---
title: Investigating Error Logs Using LangGraph, LangChain and Watsonx.ai
published: true
description: In this post we are going to explore how to use GenAI to investigate (error) logs using LangGraph, LangChain and Watsonx.ai, Python and Plotly Dash.
tags: langchain, showdev, genai, python
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/lnytsmt56r5qgxg07aml.png
---

## Introduction

When dealing with production systems, observability plays a key role. It is a vital component of incident investigations, the foundation for monitoring and alerting, and incredibly useful for validation of new functionality, improvements, or bug fixes being shipped. Application logs are a big part of observability.[^sawmills] Logs can help us understand what the system was doing at any particular point in time with a high degree of granularity.

[^sawmills]: According to the [Sawmills Observability Report 2025](https://www.sawmills.ai/observability-report-2025), logs are the main course of spend in observability, too.

However, understanding application logs can be difficult. First, there can be many logs and finding the relevant ones is difficult. Indexing the logs and using a search engine to query them helps, but it cannot tell you which logs are related to the issue you are investigating. When I see an error in the logs that correlates with the timing of the incident, I usually ask myself a bunch of follow-up questions:

- Is the error related to or possibly the root cause of the issue?
- Is this error a known problem?
- If it's known, has it been reported to the right team?
- If it has been reported, is it being worked on or even fixed?
- If it's fixed, is the fix rolled out to the environment I am investigating?
- If it's rolled out, why is the error still happening? Is there a regression?
- If there's a regression, has it been reported to the right team?

In the face of an incident, answering these questions can make you lose valuable time. You might suggest to simply postpone the investigation until the bleeding is stopped, but sometimes valuable information on how to stop the bleeding is hidden in the answers to these questions.

For example, there might be a bug ticket in progress in which someone commented a workaround you can apply. Or there might be a release candidate or hotfix release available you can potentially roll out prematurely. This is why I think it's valuable to investigate the logs deeply during incidents as well. I believe that GenAI can aid in answering these questions quickly for you during an investigation.

In this post we are going to explore how to use GenAI to investigate (error) logs. We are going to use IBM Watsonx.ai and LangGraph in Python. The remainder of the post is structured as follows: First, we will lay the technological foundation, introducing LangGraph, LangChain, and watsonx.ai. Then we will dive into the design and implementation of our solution. We will close the post by summarizing the main findings and giving an outlook for future work.

## LangGraph, LangChain and Watsonx.ai

LangGraph is a graph-based orchestration framework for building stateful AI workflows, such as agents. It lets you model an AI application as a directed graph, where:

- Nodes are functions (e.g., an LLM call, a tool call, or custom logic) that operate on a shared state.
- Edges define how control flows from one node to the next, including conditional branches and loops.
- State is an explicit, shared data structure (like a `dict` or `TypedDict`) that all nodes can read and update, making it easy to build long-running, stateful agents.

LangChain is often used as a building block within LangGraph nodes. It is a library for connecting LLMs to data and tools. By combining LangChain and LangGraph, you can build AI agents that can reason and act in cycles, adding a human in the loop as needed.

Watsonx.ai is an enterprise AI solution by IBM, which among other functionality, offers managed LLMs. We are going to combine these three tools to build an AI agent to investigate our logs. The required functionality is provided by the following Python modules: [`ibm-watsonx-ai`](https://pypi.org/project/ibm-watsonx-ai/), [`langgraph`](https://pypi.org/project/langgraph/), and [`langchain-ibm`](https://pypi.org/project/langchain-ibm/).

To illustrate how the libraries interact, let's look at a simple example. The following code implements a basic agent that has access to a tool to get the weather in a city. We are using the `create_agent` (successor to `create_react_agent`) helper function, which creates a pre-built agent graph representing a chat and tool-calling loop maintaining the message history in the global state.

```python
llm = ChatWatsonx(
    model_id="meta-llama/llama-3-70b-instruct",
    url=os.getenv("WATSONX_URL"),
)

def get_weather(city: str) -> str:
    return f"Weather in {city}: 30°C and sunny."

agent = create_agent(llm, tools=[get_weather])

agent.invoke({"messages": [
    {"role": "user", "content": "What is the weather in Berlin?"}
]})
```

For more complex applications, you can build your own graph, e.g. by utilizing the [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api). Let's build our log investigation agent next.

## Log Investigation Agent

### Scope

In the introduction, I shared a few questions we'd like the agent to answer. In the context of this post, let's focus on the following initial high-level functionality:

- Search relevant work / tickets / conversations to the log. We'll search two systems in parallel to demonstrate how to parallelize work in LangGraph: Jira and GitHub. You might also want to integrate chats like Slack, incident tracking tools, post-mortems, or other relevant tools. If you have access to some company-wide search engine like Glean, you could call that instead of interacting with the different APIs directly.
- Gather and include operational context, such as the pod / container name and deployed version. We can use this information to assess the relevance of the found tickets and discussions.
- Investigate the relevant tickets and conversations, looking for workarounds.

I am going to wrap this into a lean [Dash](https://dash.plotly.com/) UI that will look like this:

![log investigation UI](https://github.com/FRosner/outpourings/blob/master/log_investigation/img/log_investigation.png?raw=true)

Let's dive into the implementation details. First, we are going to give a general overview of the architecture and then go into the implementation details of each step.

### Defining the State

In LangGraph, state is shared among all nodes and passed along the edges. If multiple nodes modify the same property in the state concurrently, you need to define a custom merge function. For our use case, we will store all intermediate results in the state, so that we can show it to the user after the graph completed. This helps in building trust in the agent and checking its reasoning.

Here is the base definition of our [Pydantic](https://docs.pydantic.dev/latest/) model `LogInvestigationState`. For now, I will just add the field that holds the raw log text. We will add more fields in the upcoming sections.

```python
class LogInvestigationState(BaseModel):
    # Raw log text as provided by the user
    log_text: Optional[str] = None
```

### Defining the Graph

First, let's define the high level graph architecture. The first node will inspect the provided log and derive search queries for the different systems (Jira and GitHub in our case). We don't want to search for the provided log verbatim as it might be too detailed to yield all relevant results.

After that, we'll run the search across all APIs. This can be parallelized and there is no LLM needed. We'll use conditional edges with the [`Send`](https://docs.langchain.com/oss/python/langgraph/graph-api#send) functionality, which spawns nodes on-demand for each of the found tickets. We'll then grade each of the ticket based on the high level information such as title and description given the full provided log and operational context to determine its relevancy.

After filtering out irrelevant tickets, we'll merge the graph back together. Finally, we will gather additional context for the relevant tickets, such as comments, linked PRs, etc. and submit a final LLM call that will produce a report for the user.

We'll use wrapper functions (prefixed with `node_`) that pass required dependencies such as the LLM into the actual node function, as I didn't find a way to inject dependencies such as API clients or LLM clients into the nodes otherwise. Example:

```python
model: BaseChatModel  # your ChatWatsonx instance

def node_extract_ticket_queries(state: LogInvestigationState) -> LogInvestigationState:
    return extract_ticket_queries(model, state)
```

Now let's look at the Python code that builds the graph. The `add_node` function takes two arguments: the node name and the wrapper function to execute. LangGraph passes the state (`state: LogInvestigationState`) as an argument. `add_edge` takes the source and target node name as arguments. `add_conditional_edges` takes the source node name, our function that returns a list of `Send` objects, telling which target nodes to spawn. It also takes an optional path map argument, which we'll pass so that we can visualize the graph properly.

```python
def build_graph():
    # Define dependencies and wrapper functions (node_...)
    # ...
    
    graph = StateGraph(LogInvestigationState)
    
    graph.add_node(extract_ticket_queries.__name__, node_extract_ticket_queries)
    graph.add_node(search_jira_issues.__name__, node_search_jira_issues)
    graph.add_node(search_github_issues.__name__, node_search_github_issues)
    graph.add_node(grade_jira_ticket.__name__, node_grade_jira_ticket_worker)
    graph.add_node(grade_github_ticket.__name__, node_grade_github_ticket_worker)
    graph.add_node(aggregate_jira_scores.__name__, node_aggregate_jira_scores)
    graph.add_node(aggregate_github_scores.__name__, node_aggregate_github_scores)
    graph.add_node(select_relevant_jira_issues.__name__, node_select_relevant_jira_issues)
    graph.add_node(select_relevant_github_issues.__name__, node_select_relevant_github_issues)
    graph.add_node(investigate_relevant_tickets.__name__, node_investigate_relevant_tickets)
    
    graph.set_entry_point(extract_ticket_queries.__name__)
    
    graph.add_edge(extract_ticket_queries.__name__, search_jira_issues.__name__)
    graph.add_edge(extract_ticket_queries.__name__, search_github_issues.__name__)
    
    graph.add_conditional_edges(
        search_jira_issues.__name__,
        edge_dispatch_jira_grading,
        [grade_jira_ticket.__name__],
    )
    graph.add_conditional_edges(
        search_github_issues.__name__,
        edge_dispatch_github_grading,
        [grade_github_ticket.__name__],
    )
    
    graph.add_edge(grade_jira_ticket.__name__, aggregate_jira_scores.__name__)
    graph.add_edge(grade_github_ticket.__name__, aggregate_github_scores.__name__)
    
    graph.add_edge(aggregate_jira_scores.__name__, select_relevant_jira_issues.__name__)
    graph.add_edge(aggregate_github_scores.__name__, select_relevant_github_issues.__name__)
    
    graph.add_edge(select_relevant_jira_issues.__name__, investigate_relevant_tickets.__name__)
    graph.add_edge(select_relevant_github_issues.__name__, investigate_relevant_tickets.__name__)
    
    graph.add_edge(investigate_relevant_tickets.__name__, END)
    
    return graph.compile()
```

Before we jump into the implementation of the individual steps, let's review a visual representation of the graph. LangGraph comes with some helper functions to plot the graph:

```python
compiled_graph.get_graph().draw_png("log_investigation_graph.png")
```

![log investigation graph](https://github.com/FRosner/outpourings/blob/master/log_investigation/img/log_investigation_graph.png?raw=true)

Note that the way we split work into separate nodes is a matter of taste to some extent. If a set of nodes are executed sequentially (and not concurrently), and there is no need for memory / checkpointing or other functionalities, we could've merged them into a single node. I decided to keep them separate though as we will be reporting agent progress to the user via the UI. This will be implemented later based on node callbacks. Next, let's look into some of the individual steps in more detail.

### Extracting Ticket Queries

The first node will prompt the LLM to analyze the log text and come up with queries to search for relevant information in the different systems. In my case, this will be Jira and GitHub. We'll also ask the LLM to create a summary we can use as a title for a new ticket if we decide to create one later. First, let's extend the state to store the result of this step:

```python
class LogInvestigationState(BaseModel):
    log_text: Optional[str] = None
    jql_substring: Optional[str] = None
    github_query_substring: Optional[str] = None
    ticket_summary: Optional[str] = None
```

Next, let's come up with a system prompt for the LLM that tells it what to do with the log snippet. Here's what we'll be using:

> You are given an application log snippet (may include stack traces).
> Extract:
> 1) a substring to pass to a Jira search (JQL textfields ~ "..."),
> 2) a substring to pass to a GitHub issues search query, and
> 3) a concise ticket summary suitable as a GitHub issue title.
> 
> Rules for the substrings:
> - Include information from the first line of the log, as it often contains the most relevant information.
> - Look for discriminative information that might help find this exact issue. If there is a generic exception and a specific error message, focus on the error message.
> - If there is an exception type, include it plus relevant pieces of the message if available. Including only the exception name without any discriminative parts from the error will yield too many results, especially for generic exceptions.
> - Exclude variable data (timestamps, request IDs, hostnames, memory addresses, line numbers, absolute paths).
> - For Jira, produce a substring to search for in textfields.
> - For GitHub, produce a query compatible with the GitHub Search Issues API. Prefer free text phrase(s); qualifiers like in:title or in:body are optional.
> 
> Rules for the ticket summary/title:
> - Keep it succinct (<= 12 words) and clear.
> - Focus on the core error/symptom; avoid IDs, timestamps, stack details.
> - Do not end with a period.

Now we can implement the `extract_ticket_queries` function. We are going to use structured output to extract the different fields reliably. 

```python
class TicketQueries(BaseModel):
    jql_substring: str
    github_query_substring: str
    ticket_summary: str
```

Note that you always need to sanitize LLM output, as there is no guarantee that the LLM follows your instructions reliably. This includes quoting characters that might cause issues downstream, as well as shortening results to stay within character limits (e.g. for the title). I omitted this part in the code below for readability.

```python
def extract_ticket_queries(llm: BaseChatModel, state: LogInvestigationState) -> LogInvestigationState:
    log_text = state.log_text
    system_msg = """..."""

    structured_llm = llm.with_structured_output(TicketQueries)
    data: TicketQueries = structured_llm.invoke(
        [
            SystemMessage(content=system_msg),
            HumanMessage(content=log_text),
        ]
    )

    return LogInvestigationState(
        jql_substring=escape_double_quotes(data.jql_substring),
        github_query_substring=escape_double_quotes(data.github_query_substring),
        ticket_summary=data.ticket_summary,
    )
```

Let's look at an example log text and the output of the LLM. Given the following log text:

```
ERROR [nioEventLoopGroup-5-21] 2025-10-09 06:38:16,740 BrainWasher.java:84 - Failed to brainwash tenant 41d51c90-0c8e-4db6-b0c8-d143007210f0. Timeout of 5s reached.
```

It might produce the following output:

```python
TicketQueries(
    jql_substring="Failed to brainwash tenant Timeout of 5s reached",
    github_query_substring="Failed to brainwash tenant Timeout of 5s reached",
    ticket_summary="BrainWasher.java: Failed to brainwash tenant - Timeout of 5s reached",
)
```

### Ticket Search

The code for searching tickets (or other relevant pieces of information such as post mortem documents, chat conversations, etc.) is highly dependent on the respective system / API you are integrating with. For the sake of simplicity, I am going to show only the code for searching Jira tickets using the [`jira`](https://pypi.org/project/jira/) Python package. The code for searching GitHub issues is very similar.

First, let's extend the state to store the results of the search. We'll need custom types to represent the tickets. While the client libraries come with some prebuilt types such as [`Issue`](https://jira.readthedocs.io/api.html#jira.resources.Issue), they are not consistent in the fields they have and probably not serializable (at least not in a way LangGraph can handle). Therefore, we are going to define my own types, such as `JiraTicket`, which maps the Jira issue data model to our internal data model.

```python
class JiraTicket(BaseModel):
    key: str
    url: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @classmethod
    def from_jira_issue(cls, issue: jira.resources.Issue) -> JiraTicket:
    return cls(
        key=issue.key,
        url=issue.permalink(),
        summary=issue.fields.summary,
        description=issue.fields.description,
        status=issue.fields.status.name,
    )
```

Next, let's extend the `LogInvestigationState` to store the final queries (so we can show those to the user later on), as well as the results of the search, which are candidates for being relevant tickets.

```python
class LogInvestigationState(BaseModel):
    log_text: Optional[str] = None
    jql_substring: Optional[str] = None
    jql: Optional[str] = None
    jira_candidates: Optional[Dict[str, JiraTicket]] = None
    github_query_substring: Optional[str] = None
    github_query: Optional[str] = None
    github_candidates: Optional[Dict[str, GitHubTicket]] = None
    ticket_summary: Optional[str] = None
```

Now we can implement the `search_jira_issues` function. We are going to use a custom JQL query that searches for the provided substring in the text fields of the ticket. We are also going to limit the search to a specific set of projects. You might want to adjust this to your needs, ideally making it configurable via environment variables or similar.

```python
def search_jira_issues(
    state: LogInvestigationState,
    client: JIRA = None,
) -> LogInvestigationState:
    textfield_substring = state.jql_substring
    predicates = [
        f"project in (BW, UI)",
        f'textfields ~ "{textfield_substring}"'
    ]

    jql = " AND ".join(predicates) + " ORDER BY created DESC"

    fields = "summary,description,status"
    issues = client.search_issues(jql_str=jql, maxResults=50, fields=fields)

    results: Dict[str, JiraTicket] = {
        ticket.key: ticket
        for ticket in (JiraTicket.from_jira_issue(issue) for issue in issues)
    }

    return LogInvestigationState(jira_candidates=results, jql=jql)
```

With the search results stored in the state, we can investigate each ticket in detail, determining its relevance to the full log line so that we can focus our final investigation only on relevant tickets.

### Relevance Scoring

In order to parallelize execution, we will use conditional edges spawning one worker node for each candidate ticket. First, let's define the states we need. We will need a class to hold the relevance result, which will be used for the structured LLM output, too.

```python
class TicketRelevance(BaseModel):
    relevance_score: int = Field(description=
        "Relevance score from 0-100, where 0 is completely irrelevant" + 
        "and 100 is highly relevant")
    reasoning: str = Field(description=
        "Brief explanation of why this score was assigned")
```

Then, we'll extend the shared state to store these results for each ticket in a dictionary from ticket key to relevance.

```python
class LogInvestigationState(BaseModel):
    # ... other keys defined previously ...
    jira_candidates: Optional[Dict[str, JiraTicket]] = None
    jira_ticket_relevance: Annotated[Optional[Dict[str, TicketRelevance]], merge_dicts] = None
    github_candidates: Optional[Dict[str, GitHubTicket]] = None
    github_ticket_relevance: Annotated[Optional[Dict[str, TicketRelevance]], merge_dicts] = None
```

We are using an `Annotated` type to tell LangGraph how to merge the state when multiple nodes modify the same property. In this case, we want to keep all entries in the dictionary, so we'll use a custom `merge_dicts` function. This is important because we are going to process all tickets concurrently, updating the shared state with the results.

```python
def merge_dicts(left: Optional[Dict], right: Optional[Dict]) -> Dict:
    result = {}
    if left:
        result.update(left)
    if right:
        result.update(right)
    return result
```

To spawn the grading worker nodes conditionally, we'll use the `Send` API. The conditional edges invoke a dispatcher function that returns a list of `Send` objects, each representing a worker node to spawn for the respective ticket. The worker needs to know the log text as well as the ticket information. Here we can also add additional context such as the component name that emitted the log, the deployed version, cluster information or other relevant metadata.

```python
def dispatch_jira_grading(state: LogInvestigationState) -> List[Send]:
    jira_candidates = state.jira_candidates
    log_text = state.log_text

    return [
        Send(grade_jira_ticket.__name__, JiraTicketGradeState(log_text=log_text, ticket=ticket))
        for ticket in jira_candidates.values()
    ]
```

The actual grading will be performed by `grace_jira_ticket` which invokes our LLM again. We will use a system prompt (`TICKET_RELEVANCE_SYSTEM_PROMPT`) to instruct the model what to do.

> Score the ticket from 0-100 based on how likely it is to be related to the log text:
> - 0-19: Completely unrelated
> - 20-39: Possibly related but very weak connection
> - 40-59: Moderately related, shares some keywords or concepts
> - 60-79: Likely related, similar error patterns or context
> - 80-100: Highly relevant, very similar or identical issue
> 
> When evaluating relevance, consider:
> 1. **Error/Log Message Similarity**: Does the ticket describe the same or similar error message, exception type, or log pattern?
> 2. **Entity Matching**: Does the ticket mention the same specific entities (e.g., names, UUIDs, file paths, service names, configuration keys)?
> 3. **Context Similarity**: Does the ticket describe similar circumstances, components, or operations?
> 
> Provide 2-3 sentences in the reasoning field explaining:
> - What similarities or differences you found between the log and the ticket
> - Whether specific entities or error patterns match
> - Why you assigned this particular relevance score

We'll prefix the system prompt with information on the source (e.g. that this is a Jira ticket) and provide
 the LLM with a user message that contains the ticket information.

```python
def grade_jira_ticket(llm: BaseChatModel, state: JiraTicketGradeState) -> JiraTicketGradeState:
    ticket = state.ticket
    log_text = state.log_text

    system_msg = f"""You are evaluating the relevance of a Jira ticket to a log error or issue.
{TICKET_RELEVANCE_SYSTEM_PROMPT}"""
    
    user_msg = f"""Log text:
{log_text}

Jira ticket:
Key: {ticket.key}
Summary: {ticket.summary}
Description: {ticket.description}
"""

    structured_llm = llm.with_structured_output(TicketRelevance)
    result: TicketRelevance = structured_llm.invoke([
        SystemMessage(content=system_msg), 
        HumanMessage(content=user_msg)
    ])

    return JiraTicketGradeState(jira_ticket_relevance={ticket.key: result})
```

Let's look at an example again. Given the following ticket BW-17993, the model might have the following response.

![](https://github.com/FRosner/outpourings/blob/master/log_investigation/img/jira_description.png?raw=true)

- **Relevance Score**: 100
- **Reasoning**: The log text and Jira ticket describe the same error message, exception type, and log pattern, with the same specific entity (tenant UUID) and similar circumstances (brainwash component exceeding washing timeout). The ticket and log text are almost identical, indicating a high relevance score.

After grading each ticket, we'll aggregate the results back into the main state in the `aggregate_jira_scores` and `aggregate_github_scores` nodes. This follows the map-reduce pattern as designed by LangGraph when using `Send`.

### Relevance Filtering

The relevance filtering is a trivial step, where we simply go through all tickets and select those with a relevance score above a certain threshold. The selected tickets are stored in new fields `relevant_jira_issues` and `relevant_github_issues` in the state for further investigation.

```python
class LogInvestigationState(BaseModel):
    # ... other keys defined previously ...
    relevant_jira_issues: Optional[List[JiraTicket]] = None
    relevant_github_issues: Optional[List[GitHubIssue]] = None
```

I am not going to show the code here, as it is rather trivial. Now that we have a set of relevant tickets identified, the final step is to analyze all of them in the context of the log line to produce a final report.

### Final Analysis

First, let's extend the state to store the final analysis result:

```python
class LogInvestigationState(BaseModel):
    # ... other keys defined previously ...
    analysis_result: Optional[str] = None
```

Then, let's come up with a system prompt. For each relevant ticket, we will fetch some additional information before submitting it to the LLM. This includes things like comments, linked PRs, and so on. Here is the system prompt we are going to use and the node function `investigate_relevant_tickets` implementation. 

> The user is investigating an issue that has been logged by their application.
> They will provide the log text and a list of tickets. Each ticket has a key, a title, a body, and a list of comments (optional).
> Some tickets might reference other tickets or pull requests.
> 
> Your task is to investigate the relevant tickets and provide a summary of the findings:
> 
> - Is there any workaround available for the given issue? If there is no workaround mentioned, please state that clearly.
>   Workarounds include, but are not limited to:
>     - Configuration changes such as system properties, environment variables, etc.
>     - Workload changes. If the issue can be prevented by changing the usage pattern, e.g. sending fewer or smaller requests.
> - Are there any relevant pull requests (PRs) that may contain a fix for the issue? Are they merged?
> - Focus only on insights that are relevant to the issue at hand that the SRE / production engineer is facing. Discussions that are unrelated to the operational context should be ignored.
> 
> As your answer will be embedded into an existing markdown page. If you want to structure your response, please use a simple flat hierarchy with level 5 headings (#####).

```python
def investigate_relevant_tickets(
    llm: BaseChatModel,
    state: LogInvestigationState,
    jira_client: JIRA,
    github_client: Github,
) -> LogInvestigationState:
    system_prompt = f"""..."""

    user_prompt = f"""Log text:

{state.log_text}

Relevant tickets:
"""
    most_relevant_jira_issues = state.relevant_jira_issues or []
    most_relevant_github_issues = state.relevant_github_issues or []

    if len(most_relevant_jira_issues) == 0 and len(most_relevant_github_issues) == 0:
        # We don't want the LLM to hallucinate any wrong information, so we'd rather skip the analysis
        # without any context.
        return LogInvestigationState()

    user_prompt = _add_relevant_jira_issue_context(user_prompt, most_relevant_jira_issues, jira_client)
    user_prompt = _add_relevant_github_issue_context(user_prompt, most_relevant_github_issues, github_client)

    result: BaseMessage = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    return LogInvestigationState(analysis_result=result.content)
```

The helper functions `_add_relevant_jira_issue_context` and `_add_relevant_github_issue_context` are fetching additional context. This could be moved to different nodes, too, e.g. after the relevance filtering step. In our example, this is what the final user prompt might look like:

```
Log text:
ERROR [nioEventLoopGroup-5-21] 2025-10-09 06:38:16,740 BrainWasher.java:84 - Failed to brainwash tenant 41d51c90-0c8e-4db6-b0c8-d143007210f0. Timeout of 5s reached.

Relevant tickets:

## BW-17993

### Title

Brainwash component exceeds washing timeout

### Body

The brainwash component recently failed with the following error:
ERROR [nioEventLoopGroup-5-21] 2025-10-09 06:38:16,740 BrainWasher.java:84 - Failed to brainwash tenant 41d51c90-0c8e-4db6-b0c8-d143007210f0. Timeout of 5s reached.

### Comments

Frank Rosner wrote on 2025-10-09T09:01:00.000+0000: We were able to stop the bleeding by increasing the brainwashing timeout to 10s.
-Dbrainwasher.timeout=10s
```

And that's it! If your tickets contain enough information, the LLM should be able to provide a useful analysis and suggest to increase the timeout. Before we package this into the UI, let's add some progress reporting. This will help the user to understand what is happening under the hood.

## Progress Reporting

In Dash, we will implement the graph execution as a [background callback](https://dash.plotly.com/background-callbacks). Dash callbacks are Python functions that the frontend can invoke on certain triggers, such as the user pressing a button. A background callback will be executed asynchronously, and the client can poll for updates. They can also be cancelled.

By passing the `progress` key to the `@callback` decorator we can specify which Dash component properties to update when the callback makes progress. Dash will then inject a `set_progress` function into the callback function that we can use to update the progress, e.g. by setting the value of a progress bar. In our case, we are going to use individual indicators for each relevant node, that can either represent the node being pending, started, succeeded, or failed. We can use bootstrap icons and a [Dash Bootstrap spinner](https://www.dash-bootstrap-components.com/docs/components/spinner/) component to represent those states, for example:

```python
INDICATOR_PENDING = html.I(className="bi bi-circle me-2")
INDICATOR_IN_PROGRESS = html.Span(dbc.Spinner(size="sm"), className="me-2")
INDICATOR_COMPLETED = html.I(className="bi bi-check-circle-fill text-success me-2")
INDICATOR_FAILED = html.I(className="bi bi-exclamation-circle-fill text-danger me-2")
INDICATOR_SKIPPED = html.I(className="bi bi-fast-forward-circle me-2")
```

How will we know which state each node is in? We could use [state streaming](https://docs.langchain.com/oss/python/langgraph/streaming), but I decided to go for a custom decorator that we can apply to each node function that will invoke a callback with the node name and its current phase. This also adds error handling capabilities which make the graph more resilient. We'll also add an `optional` flag that indicates that the node is not critical to the overall execution and can fail without aborting the entire graph. In that case we will not raise the exception but instead return an empty state.

```python
def callback_node(
    callback: Callable[[str, NodePhase, Any], None],
    node_name: str,
    optional: bool = False,
):
    def _decorator(fn: Callable):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            bound = inspect.signature(fn).bind_partial(*args, **kwargs)
            state = bound.arguments["state"]

            def _safe_invoke(phase: NodePhase, value: Any):
                try:
                    callback(node_name, phase, value)
                except Exception:
                    logger.exception("Callback failed for node=%s phase=%s", node_name, getattr(phase, "value", phase))

            # Before execution
            _safe_invoke(NodePhase.STARTED, state)

            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                # On failure, report FAILURE with the original state
                _safe_invoke(NodePhase.FAILURE, state)
                if optional:
                    logger.warning("Optional node %s failed; returning empty state: %s", node_name, str(e))
                    return LogInvestigationState()
                raise

            # On success, report SUCCESS with the result
            _safe_invoke(NodePhase.SUCCESS, result)
            return result

        return _wrapped

    return _decorator
```

`NodePhase` is a custom enum type that represents the different phases a node can be in:

```python
class NodePhase(Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
```

We can now use that decorator to wrap our node functions. It can map the node based on the node name passed to the decorator.

```python
# The caller has to pass a callback that will be used to call `set_progress` in the Dash callback
node_callback: Callable[[str, NodePhase, LogInvestigationState], None] = lambda x, y, z: None

@callback_node(node_callback, investigate_relevant_tickets.__name__, optional=True)
def node_investigate_relevant_tickets(state: LogInvestigationState) -> LogInvestigationState:
    with get_jira_client() as jira:
        with get_github_client() as gh:
            return investigate_relevant_tickets(model, state, jira, gh)
```

This works great for regular nodes. Dynamically generated nodes from the `Send` API are a bit more tricky. If no nodes are created, the callback will not be invoked. To address this, we can create a custom decorator for the dispatch functions and for the worker nodes which will work together. The dispatching callback marks the worker as started and have each of the worker nodes report their success or failure. I am not going to go into detail here, but feel free to leave a comment if you are curious about the implementation.

## Summary and Conclusion

In this post we have seen how to utilize LangGraph and Watsonx.ai to build a custom log investigation agent. We created a Dash UI to present the investigation progress and results to the user.

![log investigation UI](https://github.com/FRosner/outpourings/blob/master/log_investigation/img/log_investigation.png?raw=true)

The solution we created is already very useful, but of course there is always room for improvement. A few ideas come to mind:

- Use more refined search technique (e.g. vector search) to find relevant tickets and conversations
- Add more sources of information
- Add further investigation steps, such as investigating code changes, merged PR dates, releases, etc. to reliably identify whether a fix is rolled out and new regressions.
- Allow users to provide additional context

For me, this was a fun exercise and my first time working with LangGraph and LangChain. The LangChain toolstack has quite a lot of capabilities I have not explored, yet, though. Have you used any of the LangChain tools before? What was your experience? Let me know in the comments.

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).
