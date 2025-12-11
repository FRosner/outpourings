def callback_worker_dispatch(callback: Callable[[str, int], None], target_node_name: str):
    """
    Decorator factory for langgraph conditional-edge dispatcher functions that return List[Send].

    It invokes the provided callback once with:
      - name: target_node_name
      - num_sends: the number of Send objects returned
    """

    def _decorator(fn: Callable[[Any], List[Send]]):
        @wraps(fn)
        def _wrapped(*args, **kwargs) -> List[Send]:
            sends: List[Send] = fn(*args, **kwargs)
            num_sends = len(sends)

            try:
                callback(target_node_name, num_sends)
            except Exception:
                logger.exception("Callback failed for worker-dispatch target=%s", target_node_name)

            return sends

        return _wrapped

    return _decorator

def callback_worker_node(callback: Callable[[str, "NodePhase"], None], node_name: str, optional: bool = False):
    """
    Decorator factory for worker nodes (targets of Send) that reports terminal phases only
    (SUCCESS or FAILURE) via a lightweight callback.

    callback(name: str, phase: NodePhase)
    """

    def _decorator(fn: Callable):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                try:
                    callback(node_name, NodePhase.FAILURE)
                except Exception:
                    logger.exception("Worker callback failed for node=%s phase=%s", node_name, NodePhase.FAILURE.value)
                if optional:
                    logger.warning("Optional worker node %s failed; returning empty state: %s", node_name, str(e))
                    return LogInvestigationState(optional_nodes_failed=True)
                raise

            try:
                callback(node_name, NodePhase.SUCCESS)
            except Exception:
                logger.exception("Worker callback failed for node=%s phase=%s", node_name, NodePhase.SUCCESS.value)
            return result

        return _wrapped

    return _decorator

@callback_worker_node(worker_node_callback, grade_github_ticket.__name__, optional=True)
def node_grade_github_ticket_worker(state: GitHubTicketGradeState) -> GitHubTicketGradeState:
    return grade_github_ticket(model, state)

@callback_worker_dispatch(worker_dispatch_callback, grade_jira_ticket.__name__)
def edge_dispatch_jira_grading(state: LogInvestigationState) -> List[Send]:
    return dispatch_jira_grading(state)


def _jira_issue_link(issue_key):
    return html.A(issue_key, href=f"{config.JIRA_ISSUE_BASE_URL}{issue_key}", target="_blank")


def _github_issue_link_from_ticket(ticket: GitHubIssue):
    repo = ticket.repository_name if ticket else None
    number = ticket.number if ticket else None
    url = ticket.url if ticket else None
    label = f"{repo}/{number}" if repo and number is not None else f"#{number}"
    return html.A(label, href=url, target="_blank") if url else html.Span(label)


def _github_issue_link_from_key(key, candidates):
    ticket = (candidates or {}).get(key)
    if ticket:
        return _github_issue_link_from_ticket(ticket)
    if "-" in str(key):
        repo, suffix = str(key).rsplit("-", 1)
        label = f"{repo}/{suffix}"
    else:
        label = f"#{key}"
    return html.Span(label)


def _render_jira_results(result):
    candidates = result.jira_candidates or {}

    items = []
    for c in candidates.values():
        key = c.key if c else None
        if not key:
            continue
        summary = (c.summary or "") if c else ""
        items.append(html.Li([_jira_issue_link(key), f": {summary}"]))

    if items:
        return [
            html.Span("Found the following related Jira issues:"),
            html.Ul(items),
        ]
    else:
        return [
            html.Span("Found no related Jira issues."),
        ]


def _render_github_results(result):
    candidates = result.github_candidates or {}

    items = []
    for c in candidates.values():
        items.append(html.Li([_github_issue_link_from_ticket(c), f": {c.title}"]))

    if items:
        return [
            html.Span("Found the following related GitHub issues:"),
            html.Ul(items),
        ]
    else:
        return [
            html.Span("Found no related GitHub issues."),
        ]


def _render_jira_aggregation_results(result: LogInvestigationState):
    scores = result.jira_ticket_relevance
    if not scores:
        return [
            html.Span("No Jira issues found."),
        ]
    return [
        html.Span("Relevance scores for Jira issues:"),
        html.Ul(
            [
                html.Li([_jira_issue_link(key), f": {scores[key].relevance_score} - {scores[key].reasoning}"])
                for key in scores
            ]
        ),
    ]


def _render_github_aggregation_results(result: LogInvestigationState):
    scores = result.github_ticket_relevance
    if not scores:
        return [
            html.Span("No GitHub issues found."),
        ]
    candidates = result.github_candidates or {}
    return [
        html.Span("Relevance scores for GitHub issues:"),
        html.Ul(
            [
                html.Li(
                    [
                        _github_issue_link_from_key(key, candidates),
                        f": {scores[key].relevance_score} - {scores[key].reasoning}",
                    ]
                )
                for key in scores
            ]
        ),
    ]


def _render_relevant_jira_issues(state: LogInvestigationState):
    issues = state.relevant_jira_issues or []
    if not issues:
        return [html.Span("No relevant Jira issues found.")]
    return html.Ul([html.Li([_jira_issue_link(t.key), f": {t.summary}"]) for t in issues])


def _render_relevant_github_issues(state: LogInvestigationState):
    issues = state.relevant_github_issues or []
    if not issues:
        return [html.Span("No relevant GitHub issues found.")]
    return html.Ul([html.Li([_github_issue_link_from_ticket(t), f": {t.title}"]) for t in issues])


@callback(
    Output(LOGS_INVESTIGATE_MODAL_ID, "is_open", allow_duplicate=True),
    Input(LOGS_INVESTIGATE_BUTTON_ID, "n_clicks"),
    prevent_initial_call=True,
)
def open_investigation_modal(n_clicks):
    return bool(n_clicks)


@callback(
    Output(LOGS_INVESTIGATE_START_BUTTON_ID, "disabled", allow_duplicate=True),
    Input(LOGS_INVESTIGATE_INPUT_ID, "value"),
    prevent_initial_call=True,
)
def update_investigation_start_button_disabled(log_text):
    text = (log_text or "").strip()
    return text == ""


def _create_intermediate_result(node: str, state: LogInvestigationState, phase: NodePhase):
    if phase == NodePhase.FAILURE:
        # TODO add the error message to the results so you don't have to check the logs
        return "Step failed. Please check the logs."
    elif phase == NodePhase.STARTED:
        if node == extract_ticket_queries.__name__:
            return f"Extracting ticket queries from provided log..."
        elif node == search_jira_issues.__name__:
            return f"Searching Jira for issues related to the provided log..."
        elif node == search_github_issues.__name__:
            return f"Searching GitHub for issues related to the provided log..."
        elif node == aggregate_jira_scores.__name__:
            return f"Grading Jira issue relevance..."
        elif node == aggregate_github_scores.__name__:
            return f"Grading GitHub issue relevance..."
        elif node == select_relevant_jira_issues.__name__:
            return f"Selecting most relevant Jira issues..."
        elif node == select_relevant_github_issues.__name__:
            return f"Selecting most relevant GitHub issues..."
        else:
            return "Step is in progress, please be patient..."
    elif phase == NodePhase.SUCCESS:
        if node == extract_ticket_queries.__name__:
            return [
                html.Span("Extracted ticket queries from provided log:"),
                html.Ul(
                    [
                        html.Li(["Jira: ", html.Code(state.jql_substring)]),
                        html.Li(["GitHub: ", html.Code(state.github_query_substring)]),
                    ]
                ),
            ]
        elif node == search_jira_issues.__name__:
            return _render_jira_results(state)
        elif node == search_github_issues.__name__:
            return _render_github_results(state)
        elif node == aggregate_jira_scores.__name__:
            return _render_jira_aggregation_results(state)
        elif node == aggregate_github_scores.__name__:
            return _render_github_aggregation_results(state)
        elif node == select_relevant_jira_issues.__name__:
            return _render_relevant_jira_issues(state)
        elif node == select_relevant_github_issues.__name__:
            return _render_relevant_github_issues(state)
        else:
            return "Step completed."


def _create_progress_outputs(progress_updates):
    outputs = []
    for node in progress_updates:
        outputs.append(progress_updates[node][logs_investigate_step_indicator_progress_id(node)])
        outputs.append(progress_updates[node][logs_investigate_step_indicator_results_id(node)])
    return outputs


launch_log_investigation_progress = []
for node in LOGS_INVESTIGATION_NODE_NAMES:
    launch_log_investigation_progress.append(
        Output(logs_investigate_step_indicator_progress_id(node), "children", allow_duplicate=True)
    )
    launch_log_investigation_progress.append(
        Output(logs_investigate_step_indicator_results_id(node), "children", allow_duplicate=True)
    )


@callback(
    [
        Output(LOGS_INVESTIGATE_INPUT_ID, "value"),
        Output(LOGS_INVESTIGATE_RESULTS_ID, "children", allow_duplicate=True),
        *launch_log_investigation_progress,
    ],
    Input(LOGS_INVESTIGATE_MODAL_ID, "is_open"),
    prevent_initial_call=True,
)
def reset_logs_investigation_form(is_open):
    """
    This callback resets the investigation form, progress indicators and results when the modal is closed.
    """
    if is_open:
        # Don't reset the form when the modal is opened
        raise PreventUpdate

    resets = ["", None]
    resets.extend([LOGS_INDICATOR_PENDING, ""] * int((len(launch_log_investigation_progress) / 2)))
    return tuple(resets)


@callback(
    Output(LOGS_INVESTIGATE_RESULTS_ID, "children"),
    Input(LOGS_INVESTIGATE_START_BUTTON_ID, "n_clicks"),
    State(LOGS_INVESTIGATE_INPUT_ID, "value"),
    State(LOGS_INVESTIGATE_POD_INFO_STORE_ID, "data"),
    running=[
        (Output(LOGS_INVESTIGATE_START_BUTTON_ID, "disabled", allow_duplicate=True), True, False),
        (Output(LOGS_INVESTIGATE_INPUT_ID, "disabled"), True, False),
        (Output(LOGS_INVESTIGATE_RESULT_AREA_ID, "style"), {}, {}),
    ],
    # Every node has two progress components: an indicator and intermediate results
    progress=launch_log_investigation_progress,
    cancel=[Input(LOGS_INVESTIGATE_MODAL_ID, "is_open")],
    background=True,
    prevent_initial_call=True,
)
def log_investigation_callback(set_progress, n_clicks, log_text, pod_info, author=None):
    """
    Run the log investigation agent graph. We're passing callbacks into the graph
    that update the progress indicators based on which nodes have been called / completed.
    To avoid race conditions if callbacks were to be called concurrently,
    we synchronize them using a local lock.

    Note that we have to maintain a progress state per node, as the set_progress callback does
    not like getting called with dash.no_update (that gives a React error). So we have to send
    the full progress array every time we update any of the indicators.
    """
    author = author or get_user()
    result_components, results = _launch_log_investigation(set_progress, log_text, pod_info)
    follow_up_components = _render_follow_up_actions(results, author)
    return [*result_components, *follow_up_components]


def _launch_log_investigation(set_progress, log_text, pod_info) -> tuple[list, LogInvestigationState]:
    return_children = []
    result: LogInvestigationState = LogInvestigationState()
    try:
        text = (log_text or "").strip()
        progress_updates = {}
        for node in LOGS_INVESTIGATION_NODE_NAMES:
            progress_updates[node] = {
                logs_investigate_step_indicator_progress_id(node): (
                    LOGS_INDICATOR_IN_PROGRESS if node == extract_ticket_queries.__name__ else LOGS_INDICATOR_PENDING
                ),
                logs_investigate_step_indicator_results_id(node): "",
            }
        # Set initial progress with the first node pending
        set_progress(tuple(_create_progress_outputs(progress_updates)))

        # Track per-node worker progress
        worker_progress = {}

        progress_lock = Lock()

        @synchronized(progress_lock)
        def node_progress_callback(node: str, phase: NodePhase, state: LogInvestigationState):
            if phase == NodePhase.STARTED:
                indicator = LOGS_INDICATOR_IN_PROGRESS
            elif phase == NodePhase.SUCCESS:
                indicator = LOGS_INDICATOR_COMPLETED
            else:
                indicator = LOGS_INDICATOR_FAILED
            results = _create_intermediate_result(node, state, phase)

            progress_updates[node] = {
                logs_investigate_step_indicator_progress_id(node): indicator,
                logs_investigate_step_indicator_results_id(node): results,
            }
            set_progress(tuple(_create_progress_outputs(progress_updates)))

        @synchronized(progress_lock)
        def worker_dispatch_callback(
                target_node_name: str,
                num_sends: int,
        ):
            if not num_sends or num_sends <= 0:
                progress_updates[target_node_name] = {
                    logs_investigate_step_indicator_progress_id(target_node_name): LOGS_INDICATOR_SKIPPED,
                    logs_investigate_step_indicator_results_id(target_node_name): "There was nothing to do.",
                }
                set_progress(tuple(_create_progress_outputs(progress_updates)))
                return
            success, failure = 0, 0
            worker_progress[target_node_name] = {"num_sends": num_sends, "success": success, "failure": failure}
            progress_updates[target_node_name] = {
                logs_investigate_step_indicator_progress_id(target_node_name): LOGS_INDICATOR_PENDING,
                logs_investigate_step_indicator_results_id(target_node_name): dbc.Progress(
                    [
                        dbc.Progress(value=success, color="success", bar=True, label=f"0/{num_sends}"),
                        dbc.Progress(value=failure, color="danger", bar=True),
                    ],
                    style={"height": "12px", "width": "50%"},
                ),
            }
            set_progress(tuple(_create_progress_outputs(progress_updates)))

        @synchronized(progress_lock)
        def worker_node_callback(node_name: str, phase: NodePhase):
            worker = worker_progress.get(node_name)
            if not worker:
                return
            if phase == NodePhase.SUCCESS:
                worker["success"] = worker.get("success", 0) + 1
            elif phase == NodePhase.FAILURE:
                worker["failure"] = worker.get("failure", 0) + 1
            else:
                return

            success = worker.get("success", 0)
            failure = worker.get("failure", 0)
            total = worker["num_sends"]
            completed = success + failure

            indicator = LOGS_INDICATOR_IN_PROGRESS if completed < total else LOGS_INDICATOR_COMPLETED

            # Compute percentages for stacked progress bar
            success_pct = int(success * 100 / total) if total else 0
            failure_pct = int(failure * 100 / total) if total else 0

            progress_updates[node_name] = {
                logs_investigate_step_indicator_progress_id(node_name): indicator,
                logs_investigate_step_indicator_results_id(node_name): html.P(
                    dbc.Progress(
                        [
                            dbc.Progress(value=success_pct, color="success", bar=True, label=f"{completed}/{total}"),
                            dbc.Progress(value=failure_pct, color="danger", bar=True),
                        ],
                        style={"height": "12px", "width": "50%"},
                    )
                ),
            }
            set_progress(tuple(_create_progress_outputs(progress_updates)))

        result: LogInvestigationState = investigate_log(
            text,
            node_callback=node_progress_callback,
            worker_dispatch_callback=worker_dispatch_callback,
            worker_node_callback=worker_node_callback,
            pod_info=pod_info,
        )
        if result.optional_nodes_failed:
            return_children.append(
                dbc.Alert(
                    "⚠️ The results below may be incomplete as some intermediate steps failed. Please check the logs for more information.",
                    color="light",
                )
            )

        relevant_jira_issues = result.relevant_jira_issues or []
        relevant_github_issues = result.relevant_github_issues or []

        return_children.append(H4("Relevant Tickets"))
        if not relevant_jira_issues and not relevant_github_issues:
            return_children.append(
                html.P(
                    [
                        "No relevant tickets have been found that appear to be related to the provided log. ",
                        "If you think the log indicates an issue, consider filing a new ticket.",
                    ]
                )
            )
        else:
            return_children.append(html.P("We found the following tickets related to the provided log."))

        if relevant_github_issues:
            return_children.append(
                html.Ul(
                    [
                        html.Li(
                            [
                                ticket_status_badge(t.status),
                                " ",
                                _github_issue_link_from_ticket(t),
                                f": {t.title}",
                            ]
                        )
                        for t in relevant_github_issues
                    ]
                )
            )

        if relevant_jira_issues:
            return_children.append(
                html.Ul(
                    [
                        html.Li(
                            [
                                ticket_status_badge(t.status),
                                " ",
                                _jira_issue_link(t.key),
                                f": {t.summary}",
                            ]
                        )
                        for t in relevant_jira_issues
                    ]
                )
            )

        if result.analysis_result:
            return_children.append(H4("Analysis"))
            return_children.append(dcc.Markdown(result.analysis_result))

        # Mark any remaining pending nodes as skipped
        with progress_lock:
            for node in progress_updates:
                progress_id = logs_investigate_step_indicator_progress_id(node)
                results_id = logs_investigate_step_indicator_results_id(node)
                if progress_updates[node].get(progress_id) == LOGS_INDICATOR_PENDING:
                    progress_updates[node][progress_id] = LOGS_INDICATOR_SKIPPED
                    progress_updates[node][results_id] = "There was nothing to do."
            set_progress(tuple(_create_progress_outputs(progress_updates)))

    except Exception as e:
        logging.getLogger(__name__).exception("Log investigation failed")
        return_children.append(html.P(f"Log investigation failed: {e}"))

    return return_children, result


def _render_follow_up_actions(result: LogInvestigationState, author: str):
    return_children = [H4("Follow-up Actions")]
    relevant_github_tickets = result.relevant_github_issues or []

    # Prepare the store so the click callback can access title/body without recomputing
    new_github_issue_title, new_github_issue_body = create_new_github_issue_payload(result, author=author)
    store = dcc.Store(
        id=LOGS_CREATE_GITHUB_ISSUE_STORE_ID,
        data={"title": new_github_issue_title, "body": new_github_issue_body},
    )

    if not relevant_github_tickets:
        action = [
            "Since no relevant GitHub issues have been found, would you like to ",
            html.A("create one", href="#", id=LOGS_CREATE_GITHUB_ISSUE_LINK_ID),
            "?",
            html.Span(id=LOGS_CREATE_GITHUB_ISSUE_RESULT_ID),
        ]
    else:
        action = [
            "If you think the GitHub issues found are not relevant, you can ",
            html.A("create a new one", href="#", id=LOGS_CREATE_GITHUB_ISSUE_LINK_ID),
            ".",
            html.Span(id=LOGS_CREATE_GITHUB_ISSUE_RESULT_ID),
        ]

    return_children.append(html.Ul([html.Li(action)]))
    return_children.append(store)
    return return_children


@callback(
    Output(LOGS_CREATE_GITHUB_ISSUE_RESULT_ID, "children"),
    Input(LOGS_CREATE_GITHUB_ISSUE_LINK_ID, "n_clicks"),
    State(LOGS_CREATE_GITHUB_ISSUE_STORE_ID, "data"),
    running=[
        (Output(LOGS_CREATE_GITHUB_ISSUE_LINK_ID, "disabled"), True, True),
        (Output(LOGS_CREATE_GITHUB_ISSUE_LINK_ID, "disable_n_clicks"), True, True),
        (Output(LOGS_CREATE_GITHUB_ISSUE_LINK_ID, "href"), None, None),
        (Output(LOGS_CREATE_GITHUB_ISSUE_RESULT_ID, "children"), [" ", dbc.Spinner(size="sm")], None),
    ],
    prevent_initial_call=True,
)
def create_github_issue(n_clicks, issue_payload):
    title = (issue_payload or {}).get("title")
    body = (issue_payload or {}).get("body")

    try:
        with get_github_client() as gh:
            repo = gh.get_repo(CNDB_REPO)
            issue = repo.create_issue(title=title, body=body)
            github_issue = GitHubIssue.from_github_issue_search_result(issue)
            link = _github_issue_link_from_ticket(github_issue)
            return html.Span([" (✅ ", link, ")"])
    except Exception as e:
        return html.Span(f" (❌ Failed to create GitHub issue: {e})")


def ticket_status_badge(status: str):
    if status is None or status.strip() == "":
        status = "Unknown"

    lower_status = status.lower()
    if (
            "closed" in lower_status
            or "resolved" in lower_status
            or "done" in lower_status
            or "released" in lower_status
            or "complete" in lower_status
    ):
        color = "success"
    elif "won't" in lower_status or "blocked" in lower_status or "rejected" in lower_status:
        color = "danger"
    else:
        color = "secondary"
    # We fix the width to 80px to avoid the layout being inconsistent across different statuses
    return dbc.Badge(status, color=color, pill=True, style={"width": "80px"})
