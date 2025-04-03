from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.sandbox.client import SANDBOX_CLIENT
from app.schema import ROLE_TYPE, AgentState, Memory, Message, Role


class BaseAgent(BaseModel, ABC):
    """Abstract base class for managing agent state and execution.

    Provides foundational functionality for state transitions, memory management,
    and a step-based execution loop. Subclasses must implement the `step` method.
    """

    # Core attributes
    name: str = Field(..., description="Unique name of the agent")
    description: Optional[str] = Field(None, description="Optional agent description")

    # Prompts
    system_prompt: Optional[str] = Field(
        None, description="System-level instruction prompt"
    )
    next_step_prompt: Optional[str] = Field(
        None, description="Prompt for determining next action"
    )

    # Dependencies
    llm: LLM = Field(default_factory=LLM, description="Language model instance")
    memory: Memory = Field(default_factory=Memory, description="Agent's memory store")
    state: AgentState = Field(
        default=AgentState.IDLE, description="Current agent state"
    )

    # Execution control
    max_steps: int = Field(default=10, description="Maximum steps before termination")
    current_step: int = Field(default=0, description="Current step in execution")

    duplicate_threshold: int = 2

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for flexibility in subclasses

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """Initialize agent with default settings if not provided."""
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())
        if not isinstance(self.memory, Memory):
            self.memory = Memory()
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """Context manager for safe agent state transitions.

        Args:
            new_state: The state to transition to during the context.

        Yields:
            None: Allows execution within the new state.

        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # Transition to ERROR on failure
            raise e
        finally:
            self.state = previous_state  # Revert to previous state

    def update_memory(
        self,
        role: ROLE_TYPE,  # type: ignore
        content: str,
        base64_image: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Add a message to the agent's memory.

        Args:
            role: The role of the message sender (user, system, assistant, tool).
            content: The message content.
            base64_image: Optional base64 encoded image.
            **kwargs: Additional arguments (e.g., tool_call_id for tool messages).

        Raises:
            ValueError: If the role is unsupported.
        """
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")

        # Create message with appropriate parameters based on role
        kwargs = {"base64_image": base64_image, **(kwargs if role == "tool" else {})}
        self.memory.add_message(message_map[role](content, **kwargs))

    async def run(self, user_query: str, system_prompt: Optional[str] = None) -> str:
        """Run agent with input user query and optional system prompt.

        Args:
            user_query: User query to run the agent with
            system_prompt: Optional system prompt override

        Returns:
            Execution result as a string
        """
        if self.state == AgentState.RUNNING:
            logger.warning(f"{self.name} already running!")
            return "Already running, please wait."

        if system_prompt:
            self.system_prompt = system_prompt

        self.state = AgentState.RUNNING
        self.memory.add_message(Message.user_message(user_query))

        try:
            # Run the agent through steps until finished
            step_count = 0
            while self.state == AgentState.RUNNING and step_count < self.max_steps:
                step_count += 1
                logger.debug(f"Executing step {step_count}")
                try:
                    step_result = await self.step()
                    if step_result is False:
                        self.state = AgentState.FINISHED

                except Exception as e:
                    if "Messages with role 'tool' must be a response to a preceding message with 'tool_calls'" in str(e):
                        # 工具消息格式错误，清理历史中的无效工具消息
                        logger.warning("检测到工具消息格式错误，尝试修复...")
                        self._clean_invalid_tool_messages()
                        # 添加警告消息
                        self.memory.add_message(
                            Message.assistant_message("由于工具消息格式错误，已重置工具状态。继续执行...")
                        )
                        # 继续执行
                        continue
                    else:
                        # 其他错误，正常处理
                        logger.error(f"Error in agent step: {e}")
                        self.state = AgentState.ERROR
                        self.memory.add_message(
                            Message.assistant_message(f"Error occurred: {str(e)}")
                        )
                        raise

            if step_count >= self.max_steps and self.state != AgentState.FINISHED:
                logger.warning(f"{self.name} reached max steps ({self.max_steps})")
                self.memory.add_message(
                    Message.assistant_message(
                        f"Maximum steps limit ({self.max_steps}) reached. Operation terminated."
                    )
                )

            # Gather final result as a summary of all assistant messages
            return self.get_result_string()

        except Exception as e:
            logger.error(f"Error in agent run: {e}")
            self.state = AgentState.ERROR
            return f"Error running {self.name} agent: {str(e)}"
        finally:
            # Reset state to allow reuse
            self.state = AgentState.IDLE

    def _clean_invalid_tool_messages(self):
        """清理内存中的无效工具消息（没有对应工具调用的工具消息）"""
        if not self.memory or not self.memory.messages:
            return

        # 收集所有有效的工具调用ID
        tool_calls_ids = set()
        for msg in self.memory.messages:
            if msg.role == Role.ASSISTANT and msg.tool_calls:
                for call in msg.tool_calls:
                    if hasattr(call, "id"):
                        tool_calls_ids.add(call.id)
                    elif isinstance(call, dict) and "id" in call:
                        tool_calls_ids.add(call["id"])

        # 过滤掉无效的工具消息
        valid_messages = []
        for msg in self.memory.messages:
            if msg.role == Role.TOOL and msg.tool_call_id:
                if msg.tool_call_id in tool_calls_ids:
                    valid_messages.append(msg)
                else:
                    logger.warning(f"移除无效的工具消息: {msg.tool_call_id}")
            else:
                valid_messages.append(msg)

        # 更新消息历史
        self.memory.messages = valid_messages

    @abstractmethod
    async def step(self) -> str:
        """Execute a single step in the agent's workflow.

        Must be implemented by subclasses to define specific behavior.
        """

    def handle_stuck_state(self):
        """Handle stuck state by adding a prompt to change strategy"""
        stuck_prompt = "\
        Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """Check if the agent is stuck in a loop by detecting duplicate content"""
        if len(self.memory.messages) < 2:
            return False

        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        # Count identical content occurrences
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """Retrieve a list of messages from the agent's memory."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value

    def get_result_string(self) -> str:
        """收集所有助手消息并生成结果摘要。

        Returns:
            str: 所有助手消息的总结，作为执行结果
        """
        # 从内存中收集所有助手消息
        assistant_messages = [
            msg.content for msg in self.memory.messages
            if msg.role == "assistant" and msg.content
        ]

        if not assistant_messages:
            return "执行完成，但没有生成任何结果。"

        # 返回最后一条助手消息作为结果
        # 也可以选择返回所有消息的组合，视需求而定
        return assistant_messages[-1]
