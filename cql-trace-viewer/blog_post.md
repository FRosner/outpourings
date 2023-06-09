---
title: CQL Trace Viewer: Visualizing CQL Traces with Dash
published: true
description: CQL Trace Viewer is a web application that visualizes CQL traces. It's built with Python and Dash.
tags: python, cassandra, dash, visualization
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/zs9ezk582kifckj4aqnn.jpg
---

## Introduction

With the rapid growth and demand in data, the management and understanding of large volumes of data have become increasingly crucial. Cassandra Query Language (CQL), a language for communicating with the Apache Cassandra database, plays an instrumental role in this process.

CQL has many similarities with SQL, the standard language for managing data held in a relational database management system. It allows you to interact with Cassandra, such as creating, updating, and deleting tables, inserting and querying data.

However, in handling voluminous data, performance is key. That's where tracing in CQL comes in. With tracing, you can track the journey of a query as it gets executed within a cluster. This includes details about the stages a query passes through, the duration for each stage, and which nodes are involved. This detailed information can help diagnose problems and optimize performance by identifying bottlenecks or areas for improvement.

But interpreting the raw output of CQL traces can be daunting due to its verbosity and complexity. This is why visualizing these traces becomes incredibly beneficial. Visualization can simplify the interpretation of these details by providing a more intuitive and user-friendly representation. Visualizing the output allows developers and administrators to better understand the execution of queries and pinpoint performance issues more easily.

For the first version of CQL Trace Viewer, we opted for a scatter plot visualization, that shows the tracing events of each involved node on a timescale. This is how it looks:

![Image description](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/pasgxssydukqicvv0aoz.png)

In the upcoming sections, we will explore CQL tracing in detail, discuss the benefits of using the Dash Python framework for building our visualization tool, CQL Trace Viewer, and provide an overview of the implementation process.

## What is CQL Tracing?

CQL tracing is a built-in feature of Apache Cassandra, a powerful tool that developers can leverage to understand how their CQL queries are being processed internally. It provides a detailed breakdown of a query's execution path, helping you see how much time is spent at each stage and which nodes are involved in the process.

Turning on tracing is as simple as running the `TRACING ON;` command in the CQL shell before executing your query. Let's try it out in the [CQL Console](https://docs.datastax.com/en/astra-serverless/docs/connect/cql/connect-cqlsh.html) of our database created in [Astra](https://astra.datastax.com/):

```sql
cqlsh> TRACING ON;
cqlsh> SELECT * FROM testks.keyvalue limit 100;
```

After the query results we can see the following trace table:

```
 activity                                                                                                                  | timestamp                  | source       | source_elapsed | client
---------------------------------------------------------------------------------------------------------------------------+----------------------------+--------------+----------------+-----------------------------------------
                                                                                                        Execute CQL3 query | 2023-04-11 15:11:23.336000 | 172.25.225.5 |              0 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                           Parsing SELECT * FROM testks.keyvalue limit 100; [CoreThread-4] | 2023-04-11 15:11:23.336000 | 172.25.225.5 |            339 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                                        Preparing statement [CoreThread-4] | 2023-04-11 15:11:23.336000 | 172.25.225.5 |            576 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                               Computing ranges to query... [CoreThread-4] | 2023-04-11 15:11:23.337000 | 172.25.225.5 |            979 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
               Submitting range requests on 25 ranges with a concurrency of 1 (0.0 rows per range expected) [CoreThread-4] | 2023-04-11 15:11:23.337000 | 172.25.225.5 |           1166 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                      Submitted 1 concurrent range requests [CoreThread-4] | 2023-04-11 15:11:23.339000 | 172.25.225.5 |           3270 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                         Sending READS.RANGE_READ message to /172.25.188.4, size=187 bytes [CoreThread-11] | 2023-04-11 15:11:23.339000 | 172.25.225.5 |           3424 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                          Sending READS.RANGE_READ message to /172.25.146.4, size=187 bytes [CoreThread-8] | 2023-04-11 15:11:23.339000 | 172.25.225.5 |           3424 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                       READS.RANGE_READ message received from /172.25.225.5 [CoreThread-2] | 2023-04-11 15:11:23.340000 | 172.25.188.4 |             60 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
            Executing seq scan across 3 sstables for (min(-9223372036854775808), min(-9223372036854775808)] [CoreThread-2] | 2023-04-11 15:11:23.340000 | 172.25.188.4 |            357 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                    Read 100 live rows and 0 tombstone ones [CoreThread-2] | 2023-04-11 15:11:23.342000 | 172.25.188.4 |           2512 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                       Enqueuing READS.RANGE_READ response to /172.25.188.4 [CoreThread-2] | 2023-04-11 15:11:23.342000 | 172.25.188.4 |           2571 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                         Sending READS.RANGE_READ message to /172.25.225.5, size=3783 bytes [CoreThread-1] | 2023-04-11 15:11:23.342000 | 172.25.188.4 |           2758 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                       READS.RANGE_READ message received from /172.25.225.5 [CoreThread-6] | 2023-04-11 15:11:23.343000 | 172.25.146.4 |            295 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                       READS.RANGE_READ message received from /172.25.188.4 [CoreThread-4] | 2023-04-11 15:11:23.343000 | 172.25.225.5 |           7990 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                     Processing response from /172.25.188.4 [CoreThread-4] | 2023-04-11 15:11:23.343000 | 172.25.225.5 |           8047 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
            Executing seq scan across 1 sstables for (min(-9223372036854775808), min(-9223372036854775808)] [CoreThread-6] | 2023-04-11 15:11:23.357000 | 172.25.146.4 |          15388 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                    Read 100 live rows and 0 tombstone ones [CoreThread-6] | 2023-04-11 15:11:23.367000 | 172.25.146.4 |          26344 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                       Enqueuing READS.RANGE_READ response to /172.25.146.4 [CoreThread-6] | 2023-04-11 15:11:23.367000 | 172.25.146.4 |          26524 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                         Sending READS.RANGE_READ message to /172.25.225.5, size=3811 bytes [CoreThread-5] | 2023-04-11 15:11:23.367000 | 172.25.146.4 |          26889 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                       READS.RANGE_READ message received from /172.25.146.4 [CoreThread-9] | 2023-04-11 15:11:23.369000 | 172.25.225.5 |          33230 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                     Processing response from /172.25.146.4 [CoreThread-4] | 2023-04-11 15:11:23.369000 | 172.25.225.5 |          33467 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
 Didn't get enough response rows; actual rows per range: 4.0; remaining rows: 0, new concurrent requests: 1 [CoreThread-4] | 2023-04-11 15:11:23.373000 | 172.25.225.5 |          37490 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
                                                                                                          Request complete | 2023-04-11 15:11:23.373604 | 172.25.225.5 |          37604 | 90b5:897e:74c8:4fd7:8dda:e206:7a0f:32a0
```

Here, the activity column describes what is happening, the timestamp column provides the time at which the activity started, the source column indicates which node in the cluster performed the activity, and source_elapsed shows the time in microseconds since the start of query execution at the source node.

While this detailed output can be valuable, it can also be overwhelming. This is where our CQL Trace Viewer comes in, helping make sense of this output by presenting it in a more approachable and visual format.

In the next section, we'll explore why we've chosen the Dash framework for this task.

## Why Dash?

When it comes to building a web application for data visualization, choosing the right framework can make all the difference. In the case of CQL Trace Viewer, we've opted for Dash, a Python framework for building analytical web applications.

Dash is built on top of Flask, Plotly.js, and React.js, harnessing the power and flexibility of these libraries. This means that it benefits from the well-known and simple back-end capabilities of Flask, the interactive and high-quality data visualization of Plotly.js, and the reactive, component-based UI build of React.js. The combination of these technologies gives Dash a strong foundation for building data-intensive applications.

Furthermore, Dash is designed specifically for creating analytical web applications, making it an ideal choice for our visualization tool. Its interactive Plotly.js charts and graphs enable users to understand and interact with their data in a much more meaningful way than raw trace outputs can provide.

Additionally, Dash allows us to create our application solely in Python. This can significantly simplify the development process, especially for those already well-versed in Python. No JavaScript or HTML knowledge is required, although these can be used if desired.

This Python-centric approach means that the app can easily integrate with the scientific Python ecosystem. Libraries such as Pandas for data manipulation and NumPy for numerical computations can be used seamlessly within the application, further expanding its capabilities.

Moreover, Dash applications are inherently web-based and can be deployed on servers and shared over the internet. This makes CQL Trace Viewer accessible to anyone who needs to understand the inner workings of their CQL queries, anywhere, and at any time.

In the next section, we will delve into the implementation details.

## Implementation

### Setup

Before we can start implementing our app, we'll need to setup the development environment. Assuming the following `requirements.txt` file:

```
dash==2.9.3
pandas==2.0.1
```

We can create a virtual environment and install the dependencies using the following commands:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Now let's write some code!

### Application Skeleton

At a high level, implementing a Dash application involves creating a Dash instance, defining the layout of the application, and starting the server. Let's create a minimal Dash application in a file called `main.py` to see this in action.

```python
from dash import Dash, html

dash_app = Dash(__name__, title=CQL Trace Viewer)
app = dash_app.server

dash_app.layout = html.Div([])

if __name__ == "__main__":
    dash_app.run_server(debug=True)
```

The `dash_app` is the main variable to interact with our Dash application. `dash_app.server` references the embedded Flask application, which we are exposing in a seemingly unused variable `app`. This will come in handy later when we deploy our application on Google Cloud Platform (GCP). 

The `dash_app.layout` defines the layout of the application. Here, we are using the `html.Div` component to create a container for our application. The empty list `[]` indicates that the container has no children. We will add components to this container later.

The conditional `if __name__ == "__main__":` allows us to start the server in debug mode when we execute the script from the command line. The debug mode enables hot-reloading, meaning the server will automatically update whenever it detects a change in your source code, and it displays more detailed error messages in the UI.

Now that we have the skeleton of our Dash app, the next step is to populate the layout with components to interact with the CQL traces and to display the visualizations.

### Adding UI Components

The first UI component we need to add is an input field that allows users to paste their CQL trace. Let's create a text area for this purpose. To make the start screen more appealing, we will store our example trace in a file called `trace.txt` and read it into the text area when the page is loaded initially.

```python
from dash import Dash, dcc, html

with open('trace.txt', 'r') as trace_file:
    trace_input = dcc.Textarea(
        id='cql-trace',
        value=trace_file.read(),
        style={'width': '100%', 'height': 300},
    )

dash_app.layout = html.Div([
    trace_input
])
```

When starting the server using `python main.py` and navigating to `http://127.0.0.1:8050/` in our browser, we can see the result:

![CQL trace input](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/nas5wm2d3clxdg0l09bs.png)

Next, let's add a scatter plot component that will later be used to plot the parsed trace.

```python
trace_scatter = dcc.Graph(
    id='trace_scatter',
)

dash_app.layout = html.Div([
    trace_input,
    trace_scatter
])
```

And this is how the empty scatter plot looks in action:

![Empty scatter plot](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/x0x5013vkw1a60wpf9k4.png)

Now that we have the basic UI components in place, let's add some interactivity.

### Adding Callbacks

In Dash, we can process user input via callbacks. In our case, we need to define a callback function that takes the CQL trace as input, parses the output, and returns the plotly figure for the scatter plot. This function will be called whenever the user changes the value of the input field.

```python
import traceback
import pandas as pd
from dash.dependencies import Input, Output
from io import StringIO

@dash_app.callback(
    Output(trace_scatter, 'figure'),
    Input(trace_input, 'value'),
)
def parse_trace(raw_trace):
    try:
        if raw_trace:
            df = pd.read_csv(StringIO(raw_trace), sep='\s*\|\s*', header=0, skiprows=[1], engine='python')
            scatter_fig = build_scatter_fig(df)
            return scatter_fig
        else:
            return {}
    except Exception:
        traceback.print_exc()
```

The `@dash_app.callback` decorator defines the callback function. The `Output` and `Input` objects specify the components and their corresponding properties that are used as input and output for the callback. In our case, the `trace_input` is the input component, and the `trace_scatter` is the output component. The `figure` property of the `trace_scatter` component is used as the output value.

The callback function takes the raw trace as input and parses it into a Pandas DataFrame. We can use the `read_csv` function to parse the table. As a separator we use `'\s*\|\s*'`, which splits the values based on `|` and trims any whitespaces at the same time. The table header is in the first line and we need to skip the second line because it does not contain any data.

The `build_scatter_fig` function is a helper function that creates the plotly figure for the scatter plot. We will implement this function in the next subsection.

### Building the Plotly Figure

To build our scatter plot, we have to perform some data transformations. Specifically, we need to compute an absolute timestamp for each activity that we can plot on the x-axis, as well as build a value to show on the y-axis.

To show the activities over time, we could plot the `timestamp` column on the x-axis. However, the `timestamp` has only millisecond accuracy and is not updated on every activity. The `source_elapsed` column, on the other hand, is a monotonic clock with microsecond accuracy. There is a catch, however, because `source_elapsed` represents the elapsed time in each node from the start of its tracing activity.

To get absolute, microsecond accurate timestamps for each activity, we need to calculate a root timestamp for each node. We can do this by subtracting the `source_elapsed` from the `timestamp` of the first activity in each node. While this does not take clock drift between the nodes into account, it is the best we can do.

To build the y-axis value, we can simply concatenate the `source` and `activity` columns. This will give us a unique value for each activity in the trace. Finally, we want to group activities by their source and color them accordingly. This is achieved by collecting the activities for each source in the dictionary `trace_activities` and then flattening the output into a single list which we can transform back into a dataframe and use as the input for the scatter plot.

Here goes the code:

```python
import plotly.express as px
import datetime

def build_scatter_fig(df):
    source_root_timestamps = {}
    trace_activities = {}

    for index, row in df.iterrows():
        source = row['source']
        row['source_activity'] = "{}: {}".format(row['source'], row['activity'])
        activity_timestamp = datetime.datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
        elapsed_micros = 0

        try:
            elapsed_micros = int(row['source_elapsed'])
        except ValueError:
            pass
            # do nothing, this is probably just a `--` value

        if source not in source_root_timestamps:
            source_root_timestamps[source] = activity_timestamp - datetime.timedelta(microseconds=elapsed_micros)
        if source not in trace_activities:
            trace_activities[source] = []

        activity_elapsed_timestamp = source_root_timestamps[source] + datetime.timedelta(microseconds=elapsed_micros)

        trace_activity = {'activity': row['activity'], 'timestamp': activity_timestamp, 'source_activity': row['source_activity'],
                          'start': activity_elapsed_timestamp, 'source': source}
        trace_activities[source].append(trace_activity)

    flattened_activities = [item for sublist in list(trace_activities.values()) for item in sublist]

    fig_df = pd.DataFrame.from_records(flattened_activities)
    fig = px.scatter(data_frame=fig_df, x='start', y='source_activity', color='source')
    fig.update_yaxes(autorange="reversed")
    return fig
```

Now let's see it in action!

![Scatter plot with activities](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/gqu8i0e63frkc7qbcwuf.png)

Note that this basic version does not include the code to generate the arrows for messages between nodes, which you could see in the screenshot as part of the introduction. If you are interested in this feature,
please take a look at the [complete source code](https://github.com/FRosner/cql-trace-viewer).

## Deployment

To deploy the app, we can use [Google Cloud App Engine](https://cloud.google.com/appengine), which is specifically built for server-side rendered websites. After we create a new project in the Google Cloud Console, we have to configure the `cql-trace-viewer` application.

Next, we have to create a file called `app.yaml`. In our case it is enough to specify the Python runtime and App Engine will figure out the rest based on the conventions of an existing file called `main.py` which defines an `app` variable that points to a Flask application. 

```yaml
# app.yaml
runtime: python39
```

We can then use the [Google Cloud SDK](https://cloud.google.com/sdk) to deploy the app:

```bash
gcloud app deploy
```

And it's live on https://cql-trace-viewer.ue.r.appspot.com/!

## Discussion

While parsing the traces with dash was a fun exercise, we'd like to address a couple of significant discussion points that arose during this process.

Firstly, numerous tracing tools already exist, many of which come with powerful capabilities and well-designed user interfaces. One potential improvement could be for Cassandra to offer an option to output traces in a standardized, machine-readable format. Such a format could be readily imported into any of these existing tools, simplifying the process and expanding the range of visualization and analysis options.

The second point of discussion revolves around the variability of the tracing output, particularly concerning the activities, which depends heavily on the database implementation and configuration. It's worth noting that the activities listed in tracing outputs can differ significantly between different versions or distributions of Cassandra.

For instance, the trace outputs between DataStax Enterprise (DSE) 6.8 and Apache Cassandra 4.0 have considerable differences. These variations imply that the parser for the CQL Trace Viewer may need to be adapted or updated according to the specific version or distribution of Cassandra being used.

## Summary

Throughout this blog post, we've journeyed through the conception, design, and development of the CQL Trace Viewer, a web application built using the Dash framework that visualizes the output of traced CQL queries.

We began by diving into CQL tracing is, exploring how it provides insights into the internal processing of CQL queries. We highlighted the need for visualization, underscoring the value of transforming raw, complex trace outputs into an intuitive and user-friendly format.

The choice of Dash as the development framework was then justified. We detailed how Dash's built-in capabilities, its roots in Flask, Plotly.js, and React.js, and its compatibility with the scientific Python ecosystem made it an ideal candidate for the task at hand.

We provided a high-level overview of the implementation, demonstrating how to create a Dash application with a text input, a plotly scatter plot figure, and a callback function that parses the input and generates the figure. We then showed how to deploy the application to Google Cloud App Engine.

Finally, we discussed the potential for future improvements, including the standardization of tracing output and the need to adapt the parser to different versions and distributions of Cassandra.

# References

- [Astra DB](https://astra.datastax.com/)
- [TRACING in DSE 6.8](https://docs.datastax.com/en/dse/6.8/cql/cql/cql_reference/cqlsh_commands/cqlshTracing.html)
- Cover image by <a href="https://unsplash.com/@polarmermaid?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Anne Nygård</a> on <a href="https://unsplash.com/photos/KWsFPbsCAPo?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
  
