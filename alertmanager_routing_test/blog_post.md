---
title: Unit Testing Alertmanager Routing and Inhibition Rules
published: true
description: Alertmanager routing trees are easy to break and hard to verify, until an incident fires at the wrong team or a customer calls. We built a Go tool that unit tests your routing and inhibition rules in CI, using alertmanager's own libraries, no live instance required.
tags: sre, devops, prometheus, alertmanager
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/9gzwu0ncmll022zb0dbm.png
---

## Introduction

There are three ways to find out your alertmanager routing tree is broken. You catch it during a careful review before anything goes wrong. You wake up at 3am to a page that went to the wrong team. Or an alert goes to the wrong receiver, nobody gets paged, and you find out when the customer calls. Most of us have experienced at least the second one.

Alertmanager routing trees grow incrementally. A new team gets added, a new severity tier is introduced, someone adds a `continue: true` flag and forgets to remove it. The config file remains valid YAML throughout. `amtool check-config` keeps returning clean. Nothing tells you that warning alerts for `DatabaseDown` are now waking up the frontend on-call instead of the backend team.

This post describes a small Go tool we built to write unit tests for alertmanager routing and inhibition rules, run them in CI, and catch these mistakes before they matter.

## The Problem

Alertmanager gives you two built-in tools for validating config:

- **`amtool check-config`** validates syntax and structure. It cannot tell you whether an alert reaches the right receiver.
- **`amtool config routes test`** lets you interactively test a single alert against the routing tree. It is useful for manual debugging but does not support batch test files, and it has no notion of inhibition. You cannot assert that a warning is suppressed when a critical is firing.

The failure modes we care about fall into two categories:

1. **Wrong receiver**: `SomeAlert` with `team=backend` ends up in the frontend Slack channel because a route was added above the team-based route without `continue: false`.
2. **Broken inhibition**: A warning fires even though a critical is active for the same alert, flooding your incident channel with noise. Or worse: warnings are being silenced when they should not be, hiding real problems.

Both are semantic errors. The config is syntactically valid; the routing logic is just wrong. Manual testing by firing test alerts into a staging alertmanager is slow, stateful, and easy to skip.

## The Solution: Automated Unit Tests

`alertmanager-routing-tests` is a Go tool that evaluates alertmanager routing and inhibition rules purely in-memory, using alertmanager's own Go libraries. No running alertmanager instance is required.

You give it an alertmanager config file and a YAML test file. It runs each test case and reports which passed and which failed:

```
  PASS Unmatched alert routes to default receiver
  PASS Watchdog alert routes to null receiver
  PASS Team A alert routes to team-a-slack
  FAIL "wrong receiver test"
       alert {alertname=SomeAlert}:
         expected: nonexistent-receiver
         actual:   default
=== routing tests: 3 passed, 1 failed ===
```

Exit code 0 means all tests passed. Exit code 1 means at least one failed, which makes it CI-friendly by default.

## How It Works

The tool imports alertmanager's own Go packages directly:

```go
import (
    amconfig "github.com/prometheus/alertmanager/config"
    "github.com/prometheus/alertmanager/dispatch"
    "github.com/prometheus/alertmanager/inhibit"
)
```

**Routing** is straightforward. The config is loaded with `amconfig.LoadFile`, and `dispatch.NewRoute(cfg.Route, nil).Match(labelSet)` returns the same receiver list that a live alertmanager would produce for that label set.

**Inhibition** is more involved. Alertmanager's inhibitor is designed to work against a live alert store. The tool works around this by implementing a minimal `provider.Alerts` interface called `fakeAlerts`, which serves a fixed set of alerts from a buffered channel:

```go
func (f *fakeAlerts) Subscribe() provider.AlertIterator {
    ch := make(chan *types.Alert, len(f.alerts))
    for _, a := range f.alerts {
        ch <- a
    }
    done := make(chan struct{})
    return provider.NewAlertIterator(ch, done, nil)
}
```

The inhibitor is constructed with this fake provider, its `Run()` goroutine is started, and after a brief pause for it to process the alert feed, `Mutes(labelSet)` is called for each alert to check whether it is suppressed.

The key design decision is that all alerts in a test case are fired together. This is what allows source alerts to inhibit target alerts within the same test case. An alert with `severity=critical` can suppress an alert with `severity=warning` when both are present in the same case.

Inhibition is checked first. If an alert is inhibited, receiver matching is skipped. Matching an inhibited alert to receivers is undefined behavior in a real alertmanager, so the test should assert inhibition explicitly.

## Writing Tests

Here is a minimal alertmanager config:

```yaml
global:
  resolve_timeout: 5m

inhibit_rules:
  - source_matchers: ['severity = "critical"']
    target_matchers: ['severity = "warning"']
    equal: [alertname]

route:
  receiver: default
  group_by: ['alertname']
  routes:
    - matchers:
        - alertname="Watchdog"
      receiver: "null"
    - matchers:
        - team="team-a"
      receiver: team-a-slack

receivers:
  - name: default
  - name: "null"
  - name: team-a-slack
```

Test files are YAML with a `tests` list. Each test case has a name and one or more alerts. Each alert has labels and an assertion: either `expected_receivers` or `expected_inhibited: true`:
- **`expected_receivers`**: ordered list of receiver names the alert must match. Order matters because alertmanager's routing order is significant when `continue: true` is used.
- **`expected_inhibited`**: set to `true` to assert the alert is suppressed. Omit (or leave false) otherwise. Do not set both on the same alert.

Here are the corresponding tests that exercise all four behaviors:

```yaml
tests:
  # Anything not matched by a specific route falls through to the default receiver.
  - name: "Unmatched alert routes to default receiver"
    alerts:
      - labels:
          alertname: SomeAlert
        expected_receivers:
          - default

  # Watchdog is a synthetic heartbeat alert. It must not page anyone.
  - name: "Watchdog alert routes to null receiver"
    alerts:
      - labels:
          alertname: Watchdog
          severity: critical
        expected_receivers:
          - "null"

  # Team-based routing: alerts with team=team-a go to team-a-slack.
  - name: "Team A alert routes to team-a-slack"
    alerts:
      - labels:
          alertname: TeamAAlert
          team: team-a
        expected_receivers:
          - team-a-slack

  # Inhibition: a critical suppresses a warning with the same alertname.
  # Both alerts are fired together so the inhibitor can evaluate the relationship.
  - name: "critical suppresses warning with same alertname"
    alerts:
      - labels:
          alertname: SomeAlert
          severity: critical
        expected_receivers:
          - default
      - labels:
          alertname: SomeAlert
          severity: warning
        expected_inhibited: true

  # Inhibition boundary: a critical for AlertOne does NOT suppress a warning
  # for AlertTwo because the inhibit rule requires equal alertname.
  - name: "critical does NOT suppress warning with different alertname"
    alerts:
      - labels:
          alertname: AlertOne
          severity: critical
        expected_receivers:
          - default
      - labels:
          alertname: AlertTwo
          severity: warning
        expected_receivers:
          - default
```

The last test case is easy to miss in manual testing. The inhibition rule says "a critical suppresses a warning with the same `alertname`." Without a test pinning this boundary, a future change to the inhibition rule could accidentally broaden the `equal` list (or remove it entirely) and start silencing warnings across unrelated alerts.

## Running the Tool

```bash
go run . example-alertmanager.yaml example-routing-tests.yaml
```

All five tests above pass against the example config. To see a failure, change an `expected_receivers` entry to a nonexistent receiver:

```
  PASS Unmatched alert routes to default receiver
  FAIL "Watchdog alert routes to null receiver"
       alert {alertname=Watchdog, severity=critical}:
         expected: nonexistent-receiver
         actual:   null
=== routing tests: 1 passed, 1 failed ===
```

The tool exits with code 1, which blocks CI.

## Integrating with CI via Helm Charts

Many teams store their alertmanager config inside a Helm chart rather than as a standalone file. The config may be embedded as a YAML string inside a values file, or rendered into a ConfigMap or ApplicationSet at deploy time.

To test the rendered config, you need to extract it from the rendered template before passing it to the tool. Here is a Makefile target that does this end-to-end:

```makefile
ROUTING_TEST_YAML := ./alertmanager-unit-tests/routing-tests.yaml

.PHONY: test
test:
    @WORKDIR=$$(mktemp -d) && \
    helm template test ./my-chart \
        -f "./alertmanager-unit-tests/values.yaml" \
        | yq 'select(.kind == "ConfigMap") | .data["alertmanager.yaml"]' \
        > "$$WORKDIR/alertmanager.yaml" && \
    cd /path/to/alertmanager-routing-tests && \
        go run . "$$WORKDIR/alertmanager.yaml" $(CURDIR)/$(ROUTING_TEST_YAML) && \
    rm -rf "$$WORKDIR"
```

The `yq` expression selects the rendered alertmanager config from the template output. Adjust the selector to match your chart's structure. If the config is embedded as a YAML string inside another resource (for example, an ArgoCD ApplicationSet), you may need `from_yaml` to parse it before extracting the alertmanager section:

```bash
| yq 'select(.kind == "ApplicationSet") \
    | .spec.template.spec.source.helm.values \
    | from_yaml \
    | .alertmanager.config'
```

With this in place, `make test` renders the chart and runs the routing tests in a single step. No live cluster, no running alertmanager. The tests run in CI the same way they run locally.

The test YAML lives next to the chart and is reviewed in the same pull requests that change the alertmanager config. Routing changes need passing tests to merge.

## Conclusion

Alertmanager routing bugs are quiet. The config is valid, deployment succeeds, and the tree looks right when you read it. You only find out something is wrong when an alert fires and the wrong team gets paged, or nobody gets paged at all, or a customer calls.

Unit tests for routing rules are not conceptually different from unit tests for application code. The logic is complex, the failure modes are silent, and the consequences are real. A test file that exercises your routing tree, including inhibition boundaries, makes routing changes reviewable and gives you a CI gate that catches regressions before they reach production.

If you manage alertmanager config, consider starting with three test cases: the default catch-all, one named receiver route, and one inhibition rule. Extend from there as your routing tree grows.

## Future Work

The most natural home for this feature is `amtool` itself. The existing `amtool config routes test` command already evaluates a single alert interactively. Extending it to accept a YAML file with multiple test cases and inhibition assertions would make batch routing tests available to the entire Prometheus community without a separate tool.

A contribution along these lines would require adding inhibition support and a test runner loop to the existing command, which is straightforward work on top of what `amtool` already does. We are considering contributing this upstream.
