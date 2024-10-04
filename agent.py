import json
from typing import List, Optional
from pydantic import BaseModel, PrivateAttr, Field
from enum import Enum
from dotenv import load_dotenv

from compositeai.agents.base_agent import (
    AgentOutput, 
    AgentStep, 
    AgentResult, 
    BaseAgent,
)
from compositeai.drivers.base_driver import (
    DriverInput, 
    DriverToolChoice, 
    DriverMessage,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ToolMessage,
)

load_dotenv()

##### AI AGENT FRAMEWORK SETUP

class NextStep(Enum):
    PLAN = 'plan'
    ACTION = 'action'
    OBSERVE = 'observe'
    OUTPUT = 'output'


class StepCheck(BaseModel):
    complete: bool = Field(description="true if the current step is complete")


class Agent(BaseAgent):
    _memory_chat: List[DriverMessage] = PrivateAttr(default=[])
    _memory_curr_execution: List[DriverMessage] = PrivateAttr(default=[])
    _next_step: NextStep = PrivateAttr(default=NextStep.PLAN)
    _num_curr_iterations: int = PrivateAttr(default=0)
    _output_format: BaseModel | None = PrivateAttr(default=None)


    def __init__(self, **data):
        # Superclass init
        super().__init__(**data)
        # Add agent description as system message for LLM
        self._memory_chat.append(
            SystemMessage(
                role="system",
                content=self.description,
            ),
        )


    def exec_init(self, task: str, input: Optional[str] = None) -> None:
        # Add additional input to task, if given
        if input:
            task = f"""
            {task}

            SOME INFO YOU ARE GIVEN TO START THE TASK:
            {input}
            """
        # Add task to LLM as a user message
        self._memory_chat.append(UserMessage(role="user", content=task))
        

    def iterate(self) -> AgentOutput:
        # Run iteration based on next step
        try:
            if self._num_curr_iterations == self.max_iterations - 1:
                return self._output()
            self._num_curr_iterations += 1

            match self._next_step:
                case NextStep.PLAN:
                    return self._plan()
                case NextStep.ACTION:
                    return self._action()
                case NextStep.OBSERVE:
                    return self._observe()
                case NextStep.OUTPUT:
                    return self._output()
        except Exception as e:
            print(str(e))
            return self._output(error=True)
            

    def _plan(self) -> AgentStep:
        # Generate a plan formatted as list of steps 
        plan_prompt = f"WRITE WHAT YOU SHOULD DO NEXT:"
        self._memory_curr_execution.append(SystemMessage(role="system", content=plan_prompt))
        messages = self._memory_chat + self._memory_curr_execution
        driver_input = DriverInput(
            messages=messages,
            temperature=0.0,
        )
        response = self.driver.generate(input=driver_input)
        self._memory_curr_execution.append(AssistantMessage(role="assistant", content=response.content))
        self._next_step = NextStep.ACTION
        return AgentStep(content=response.content)
    
    
    def _action(self) -> AgentStep:
        # Generate action based on the step
        system_message = "WORK ON WHAT YOU SHOULD DO NEXT:"
        self._memory_curr_execution.append(SystemMessage(role="system", content=system_message))
        driver_input = DriverInput(
            messages=self._memory_chat + self._memory_curr_execution,
            tools=self.tools,
            tool_choice=DriverToolChoice.AUTO,
            temperature=0.0,
        )
        response = self.driver.generate(input=driver_input)
        tool_calls = response.tool_calls

        # If no tools called, 
        if not tool_calls:
            # Record response in memory
            self._memory_curr_execution.append(AssistantMessage(role="assistant", content=response.content))
            self._next_step = NextStep.OBSERVE
            return AgentStep(content=response.content)
        
        # If tools called, go to OBSERVE step and stream tool calls as AgentStep
        else:
            tool_messages = []
            observations = ""
            for tool_call in tool_calls:
                # Get function call info
                function_name = tool_call.name
                function_args = json.loads(tool_call.args)
                tool_call_id = tool_call.id

                # Iterate through provided tools to check if driver_response function call matches one
                no_match_flag = True
                for tool in self.tools:
                    try:
                        # If match, run tool function on arguments for result, and append to memory
                        if tool.get_schema().name == function_name:
                            no_match_flag = False
                            function_result = str(tool.func(**function_args))

                            # Put condensed result into tool message
                            tool_message = ToolMessage(
                                role="tool", 
                                content=function_result,
                                tool_call_id=tool_call_id,
                            )
                            tool_messages.append(tool_message)

                            # Add to overall observations
                            observations += "\n\n" + function_result
                    except Exception as e:
                        observations += "\n\n" + f"Error: {e}"
                
                # If driver_response function call matches none of the given tools
                if no_match_flag:
                    raise Exception("Driver called function, function call does not match any of the provided tools.")
                
            # Once tool messages has been obtained from the results of function calls, add to memory
            self._memory_curr_execution.append(AssistantMessage(role="assistant", tool_calls=tool_calls))
            self._memory_curr_execution += tool_messages
            self._next_step = NextStep.OBSERVE

            # Return string concatenated version of condensed tool call results
            tool_observe = ""
            for tool_call in tool_calls:
                tool_observe += f"Calling tool:\n```json\n{tool_call.name}\n```\n"
                tool_observe += f"Parameters:\n```json\n{tool_call.args}\n```\n\n"
            tool_observe += f"Results:\n```json\n{observations}\n```"
            return AgentStep(content=tool_observe)


    def _observe(self) -> AgentStep:
        step_check_prompt = f"""
        DO YOU HAVE ENOUGH INFORMATION TO COMPLETE THE TASK?

        The output should be formatted as a JSON instance that conforms to the JSON schema below.

        As an example, for the schema {{"properties": {{"foo": {{"title": "Foo", "description": "a list of strings", "type": "array", "items": {{"type": "string"}}}}}}, "required": ["foo"]}}
        the object {{"foo": ["bar", "baz"]}} is a well-formatted instance of the schema. The object {{"properties": {{"foo": ["bar", "baz"]}}}} is not well-formatted.

        Here is the output schema:
        ```
        {StepCheck.model_json_schema()}
        ```
        """
        self._memory_curr_execution.append(SystemMessage(role="system", content=step_check_prompt))
        driver_input = DriverInput(
            messages=self._memory_chat + self._memory_curr_execution,
            temperature=0.0,
            response_format="json_object"
        )
        completed = self.driver.generate(input=driver_input)
        completed = json.loads(completed.content)["complete"]

        if completed:
            self._next_step = NextStep.OUTPUT
            self._memory_curr_execution.append(AssistantMessage(role="assistant", content="Completed Task."))
            return AgentStep(content=f"Completed Task.")
        else:
            self._next_step = NextStep.PLAN
            self._memory_curr_execution.append(AssistantMessage(role="assistant", content="Continuing Task..."))
            return AgentStep(content=f"Continuing Task...")


    def _output(self, error: bool = False) -> AgentResult:
        if error:
            agent_response = "An error occurred. Please try again."
        else:
            result_prompt = f"""
            ANSWER THE USER'S REQUEST.
            """
            self._memory_curr_execution.append(SystemMessage(role="system", content=result_prompt))
            driver_input = DriverInput(
                messages=self._memory_chat + self._memory_curr_execution,
                temperature=0.0,
            )
            agent_response = self.driver.generate(input=driver_input).content
        
        self._memory_chat.append(AssistantMessage(role="assistant", content=agent_response))

        # Remove earliest two chat messages (skipping system prompt) if more than 10 in memory
        if len(self._memory_chat) >= 10:
            self._memory_chat.pop(1)
            self._memory_chat.pop(1)

        # Reset state to intake new task
        self._next_step = NextStep.PLAN
        self._memory_curr_execution.clear()
        self._num_curr_iterations = 0

        # Return final output
        return AgentResult(content=agent_response)
    
    
    def get_memory(self) -> List[DriverMessage]:
        return self._memory_chat
