import asyncio
from typing import  TypedDict, Annotated, Literal
from pydantic import BaseModel, Field
import re

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode, tools_condition

from app.agent.tools.generate_docx import generate_word_doc_tool
from app.agent.tools.generate_ppt import create_pptx_tool
from app.agent.tools.file_handling import * 
from app.model.model_manager import ModelManager

from app.agent.sovereignty import  guard, sovereignty_tool_logger
from app.agent.sandbox_engine import sandbox

from app.agent.prompts import *
guard.start_network_monitor()




provider = "ollama"
manager = ModelManager(provider)











MAX_TRY = 5

class CodingState(TypedDict):
    task_description : str
    planned_architecture : str
    current_code : str
    error_description : str
    retries : int


def planning_code_architecture(state : CodingState):

    guard.log_event("AGENT_PHASE", "Senior Architect: Planning Architecture")
    system_prompt = planning_code_architecture_prompt
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["task_description"])]
    llm = manager.get_model("coding")
    res = llm.invoke(messages)

    return {
        "planned_architecture" : res.content
    }


def write_code(state : CodingState):

    guard.log_event("AGENT_PHASE", "Software Engineer: Generating Implementation")
    system_prompt = write_code_prompt
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["planned_architecture"])]
    llm = manager.get_model("coding")
    res = llm.invoke(messages)

    return {
        "current_code" : res.content,
    }


def execute_and_test_code(state : CodingState):

    guard.log_event("SANDBOX", "Verifying code in isolated Docker environment...")
    result = sandbox.run_code(state["current_code"])
    status = result["status"]
    stdout = result["stdout"]
    stderr = result["stderr"]

    logs = stderr if stderr else stdout

    if "no display name" in stderr or "TclError" in stderr:
        guard.log_event("SANDBOX_INFO", "GUI detected. Logic appears valid, but display is unavailable in Sandbox.")
        return {"error_description": "STATUS OK"}
    
    if status == "SUCCESS":
        guard.log_event("SANDBOX_SUCCESS", "Logic verified. No runtime errors.")
        return {"error_description": "STATUS OK"}
    else:
        guard.log_event("SANDBOX_FAILURE", f"Caught error: {status}")
        return {"error_description": f"Status: {status}\nLogs:\n{logs}"}


def decide_if_fix(state : CodingState):
    if "STATUS OK" in state["error_description"]:
        return "end"
    elif state["retries"] >= MAX_TRY:
        guard.log_event("SUBGRAPH_END", "Max retries reached. Outputting best-effort code.")
        return "end"

    return "fix_code"


def fix_code(state : CodingState):
    new_retry_count = state.get("retries", 0) + 1
    guard.log_event("AGENT_PHASE", f"Fixer: Correcting attempt {new_retry_count}")
    
    system_prompt = fix_code_prompt
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Code:\n{state['current_code']}\nError:\n{state['error_description']}")
    ]
    llm = manager.get_model("coding")
    res = llm.invoke(messages)
    return {"current_code": res.content, "retries": new_retry_count}




def coding_assistant_graph():

    sub = StateGraph(CodingState)

    sub.add_node("planner_node", planning_code_architecture)
    sub.add_node("write_code", write_code)
    sub.add_node("execute_and_test_code", execute_and_test_code)
    sub.add_node("fix_code", fix_code)

    sub.add_edge(START, "planner_node")
    sub.add_edge("planner_node", "write_code")
    sub.add_edge("write_code", "execute_and_test_code")
    sub.add_conditional_edges(
        "execute_and_test_code",
        decide_if_fix,
        {
            "fix_code": "fix_code",
            "end": END
        }
    )
    sub.add_edge("fix_code", "execute_and_test_code")

    return sub.compile()


coding_assistant_workflow = coding_assistant_graph()




def strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text





class SupervisorState(TypedDict):
    messages : Annotated[list[BaseMessage], add_messages]
    next_agent : str 
    task_complete : str
    final_response : str


class RouteDecison(BaseModel):
    reasoning: str = Field(
        description=(
            "Step-by-step reasoning about what the user is asking for. Explicitly answer: "
            "does this require WRITING NEW CODE LOGIC that must be tested (→ coding), or is "
            "it a DIRECT ACTION on existing files (delete/move/rename/copy) or plain content "
            "authoring (README/docx/pptx) with no logic to verify (→ general_qna_and_rag)?"
        )
    )
    next: Literal["coding", "general_qna_and_rag", "vision"] = Field(
        description="which agent to call next, consistent with the reasoning above"
    )






tools = [
    generate_word_doc_tool, create_pptx_tool, search_files, read_file, write_file, append_file, copy_file, move_file, delete_file, rename_file,
    create_directory, delete_directory_by_name
]

tools = [sovereignty_tool_logger(t) for t in tools]


def validate_routing(decision: RouteDecison) -> str:
    reasoning_lower = decision.reasoning.lower()
    file_action_keywords = ["delete", "remove", "rename", "move ", "copy ", "file manipulation", "file deletion"]
    code_logic_keywords = ["write code", "new function", "new script", "algorithm", "bug", "implement"]

    if decision.next == "coding" and any(k in reasoning_lower for k in file_action_keywords) \
       and not any(k in reasoning_lower for k in code_logic_keywords):
        guard.log_event("ROUTING_CORRECTION",
            "Overriding: reasoning describes a direct file action, not new code logic.")
        return "general_qna_and_rag"

    return decision.next


async def supervisor_agent(state : SupervisorState):
    system_prompt = supervisor_agent_prompt
    guard.log_event("MODEL_SELECTION", "Selecting 'SUPERVISOR-AGENT' for orchestration", model="multimodal")

    last_human_message = [m for m in state["messages"] if isinstance(m, HumanMessage)][-1:]
    
    messages = [SystemMessage(content=system_prompt)] + last_human_message

    llm = manager.get_model("multimodal")
    llm_with_schema = llm.with_structured_output(RouteDecison)

    decision = await asyncio.to_thread(llm_with_schema.invoke, messages)
    corrected_next = validate_routing(decision)
    guard.log_event("ROUTING", f"Decision: {corrected_next} | Reason: {decision.reasoning}")

    return {"next_agent": corrected_next, "messages": []}



async def coding_agent(state: SupervisorState):
    if isinstance(state["messages"][-1], ToolMessage):
        guard.log_event("AGENT_STEP", "Tool execution confirmed. Finalizing response.")
        llm = manager.get_model("coding")
        summary_res = await asyncio.to_thread(llm.invoke, state["messages"][-2:] + [
            SystemMessage(content="Provide a 1-sentence professional confirmation of the action just completed.")
        ])
        return {"messages": [summary_res], "next_agent": "end"}

    guard.log_event("MODEL_SELECTION", "Activating Coding Agent Controller", model="coding")
    guard.log_event("SUBGRAPH_START", "Starting architecture and verification loop...")

    user_task = state["messages"][-1].content
    subgraph_result = await asyncio.to_thread(
        coding_assistant_workflow.invoke,
        {"task_description": user_task, "retries": 0, "current_code": "", "error_description": ""}
    )
    verified_code = strip_code_fences(subgraph_result["current_code"])

    system_message = SystemMessage(content=coding_agent_prompt)
    llm = manager.get_model("coding")
    llm_with_tools = llm.bind_tools(tools)

    dispatch_prompt = f"""
    ### VERIFIED SOLUTION
    {verified_code}

    ### ORIGINAL INTENT
    "{user_task}"

    ### DEPLOYMENT INSTRUCTIONS
    The logic has been verified in the Docker Sandbox. Now, deploy the project:
    1. **Source Code**: Use `write_file` to save each block into its own '.py'/'.js'/etc. file.
    2. **Documentation**: Use `generate_word_doc_tool` to create a 'README.docx'.
    3. **Rules**:
       - Source files must have correct extensions.
       - DO NOT wrap code in '.md' or '.txt'.
    4. **Cleanup**: Provide only file paths and a 1-sentence summary in the final response.
    """

    try:
        res = await asyncio.to_thread(llm_with_tools.invoke, [system_message, HumanMessage(content=dispatch_prompt)])
        return {"messages": [res]}
    except Exception as e:
        guard.log_event("ERROR", f"Tool Dispatch failed: {e}")
        return {"messages": [AIMessage(content=f"I verified the code, but failed to save it: {e}")]}



async def general_agent(state : SupervisorState):

    guard.log_event("MODEL_SELECTION", "Selecting 'GENERAL-AGENT' for general question answering", model="summarization")
    system_prompt = general_agent_prompt

    recent_messages = state["messages"][-5:] 
    messages = [SystemMessage(content=system_prompt)] + recent_messages

    try:
        llm = manager.get_model("summarization")
    except ValueError as e:
        return {"messages": [AIMessage(content=f"Error: summarization model not configured ({e})")]}
    try:
        llm_with_tools = llm.bind_tools(tools)
        res = await asyncio.to_thread(llm_with_tools.invoke,messages)

        return {"messages": [res]}
    
    except Exception as e:
        return {"messages": [AIMessage(content=f"General agent error: {e}")]}






async def vision_agent(state : SupervisorState):

    guard.log_event("MODEL_SELECTION", "Selecting 'VISION-AGENT' for vision related tasks", model="vision")
    system_prompt = vision_agent_prompt

    task = [m.content for m in state["messages"] if isinstance(m, HumanMessage)][-1]

    try:
        llm = manager.get_model("vision")
    except ValueError as e:
        return {"messages": [AIMessage(content=f"Error: vision model not configured ({e})")]}
    try:
        llm_with_tools = llm.bind_tools(tools)
        res = await asyncio.to_thread(llm_with_tools.invoke,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content = task)
            ]
        )
        return {"messages": [AIMessage(content=f"[Vision Agent] {res.content}")]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Vision agent error: {e}")]}



tool_node = ToolNode(tools)






async def route_tools_back_to_agent(state : SupervisorState):
    return state["next_agent"]




def agent_workflow():

    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor_agent",supervisor_agent)
    graph.add_node("coding_agent",coding_agent)
    graph.add_node("general_agent",general_agent)
    graph.add_node("vision_agent",vision_agent)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "supervisor_agent")

    graph.add_conditional_edges(
        "supervisor_agent",
        lambda state : state["next_agent"],
        {
            "coding": "coding_agent",
            "general_qna_and_rag": "general_agent",
            "vision": "vision_agent",
        }
    )

    graph.add_conditional_edges("coding_agent", tools_condition)
    graph.add_conditional_edges("general_agent", tools_condition)
    graph.add_conditional_edges("vision_agent", tools_condition)

    graph.add_conditional_edges(
        "tools",
        route_tools_back_to_agent,
        {
            "coding": "coding_agent",
            "general_qna_and_rag": "general_agent",
            "vision" : "vision_agent"
        }
    )

    return graph.compile()


agent = agent_workflow()




async def main():
    print("\n" + "="*60)
    print("🤖 OLLAMA INTEGRATED SOVEREIGN AGENT : O.L.i.S.A")
    print("="*60)
    
    while True:
        user = input("\nAsk Query: ")
        if user.lower() in ["exit", "bye"]: break

        print("\n--- [INTERNAL TRACE] ---")
        
        current_node = None 

        async for message_chunk, metadata in agent.astream(
            {"messages" : [HumanMessage(content=user)]},
            stream_mode="messages",
        ):
            node = metadata.get("langgraph_node")
            
            if node in ("coding_agent", "general_agent", "vision_agent"):
                

                if node != current_node:
                    print(f"\n[AGENT RESPONSE ({node})]: ", end="", flush=True)
                    current_node = node
                

                if message_chunk.content:
                    print(message_chunk.content, end="", flush=True)

        print("\n" + "-"*50)

if __name__ == "__main__":
    asyncio.run(main())