---
title: Hausmeister: Automating Slack Channel Archiving Using GitHub Actions
published: true
description: How to build a Slack App that archives inactive channels using Node.js, Slack Bolt SDK, and GitHub Actions. 
tags: slack, productivity, serverless, github
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/idwsimvcfhp3gntwlb5s.png
---

## Motivation

Slack is a great communication tool, offering not only chat functionality, but also audio and video calls. Threads are a good way to discuss a message / topic in greater detail, without creating noise in the channel or creating interleaving conversations that are hard to follow. However, sometimes there are topics to discuss that will take more than a couple of messages. In this case, you can also utilize temporary, public channels.

Unfortunately, Slack does not have built-in functionality for temporary channels. Adding more and more channels, your Slack client performance will eventually grind to a halt, especially on mobile. Luckily, there are apps like [Channitor](https://happybara.gitbook.io/channitor/), which automatically archive Slack channels after a certain period of inactivity.

Channitor works great, but it misses one feature that is critical for me: I only want it to manage a subset of my channels based on the channel name. So I decided to quickly build my own Slack app "Hausmeister" that gets the job done. Hausmeister is the German word for janitor.

The remainder of this blog post will walk you through the steps required to build such an app. First, we will look at how to set up the Slack App. Then, we are going to write the app code. Finally, we will wrap the code in a GitHub action to automate the execution.

## Slack App

To create a new Slack App, simply navigate to https://api.slack.com/apps, and click "Create New App". Our app will need permissions to perform actions such as joining and archiving channels. Those permissions are managed as [Bot Token Scopes](https://api.slack.com/authentication/basics#scopes). For our app to work, we need the following scopes:

- `channels:history`
- `channels:join`
- `channels:manage`
- `channels:read`
- `chat:write`

After you added the respective scopes, they should show up like this:

![Bot Token Scopes channels:history channels:join channels:manage channels:read chat:write](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/i36fw1c52xfoyvnb2cbn.png)

Now that we have the scopes defined, it is time to install the app in your workspace. I generally recommend using a test workspace when developing your app. If you are part of a corporate workspace, your administrators might have to approve the app.

If the installation was successful, a Bot User OAuth Token should become available. You will need this later, together with the signing secret which can be obtained from the App Credentials section inside the Basic Information page of your app management UI.

Hooray! We configured everything that is required for our app. Of course, it is recommended to add some description and a profile picture so that your colleagues know what this new bot is about. Next, let's write the app code. 

## Source Code

Our app will be running on Node.js. Let's walk through what we need, step by step. The entire [source code](https://github.com/FRosner/hausmeister) is available on GitHub.

To interact with the Slack APIs, we can use [`@slack/bolt`](https://www.npmjs.com/package/@slack/bolt). Additionally, we will also install [`parse-duration`](https://www.npmjs.com/package/parse-duration) to be able to conveniently specify the maximum age of the last message in a channel before archiving it.

For maximum flexibility, we will configure the app behaviour through [environment variables](https://12factor.net/config). We need to pass:

- The Bot User OAuth Token (`HM_SLACK_BEARER_TOKEN`). This is needed to authenticate the bot with the Slack API.
- The signing secret (`HM_SLACK_SIGNING_SECRET`). This is used to validate incoming requests from Slack. Our app will not receive any requests, because we do not have any slash commands or similar, but the Bolt SDK requires us to specify the signing secret.
- A regular expression determining which channels to join and manage (`HM_SLACK_SIGNING_SECRET`). This is the cool part.
- The maximum age of the latest message in a channel before it gets archived (`HM_LAST_MESSAGE_MAX_AGE`).
- A toggle whether to actually archive channels (`HM_ARCHIVE_CHANNELS`). We can turn this off to perform a dry-run.
- A toggle whether to send a message to the channel before archiving it (`HM_SEND_MESSAGE`). Sending a message to the channel, indicating why it is being archived gives more context to the members.

The following listing shows an example invocation:

```bash
HM_SLACK_BEARER_TOKEN="xoxb-not-a-real-token" \
  HM_SLACK_SIGNING_SECRET="abcdefgnotarealsecret" \
  HM_CHANNEL_REGEX='^temp-.*' \
  HM_LAST_MESSAGE_MAX_AGE='30d' \
  HM_ARCHIVE_CHANNELS='true' \
  HM_SEND_MESSAGE='true' \
  node index.js
```

> Note that passing the credentials via environment variables comes with [certain risks](https://www.trendmicro.com/en_us/research/22/h/analyzing-hidden-danger-of-environment-variables-for-keeping-secrets.html#:~:text=However%2C%20from%20a%20cloud%20security,than%20one%20instance%20of%20compromise.). Depending on how you are deploying your application, you might want to mount secrets via files instead.

Let's get into the code! The app is so simple, we will be able to fit everything into a single `index.js` file. The following listing contains the entire app. It still has two function stubs, which we will implement in the following paragraphs.

```js
const { App } = require('@slack/bolt');
const parseDuration = require('parse-duration')

const app = new App({
  token: process.env.HM_SLACK_BEARER_TOKEN,
  signingSecret: process.env.HM_SLACK_SIGNING_SECRET
});

const sendMessage = process.env.HM_SEND_MESSAGE;
const archiveChannels = process.env.HM_ARCHIVE_CHANNELS;
const channelRegex = process.env.HM_CHANNEL_REGEX;
const lastMessageMaxAge = parseDuration(process.env.HM_LAST_MESSAGE_MAX_AGE);
console.log(`Archiving channels matching ${channelRegex} with no activity for ${lastMessageMaxAge}ms`);

const listChannels = async (listOptions) => {
  // TODO
}

const processChannel = async (c) => {
  // TODO
}

(async () => {
  const listOptions = {exclude_archived: true, types: "public_channel", limit: 200}
  const channels = listChannels(listOptions);
  const matchingChannels = channels.filter(c => c.name.match(channelRegex) != null);
  console.log(`Found ${matchingChannels.length} matching channels.`);
  await Promise.all(matchingChannels.map(processChannel));
})();
```

First, we import our dependencies and parse the configuration from the environment. The main part consists of one async function that we immediately invoke. This is needed because the Slack API invocations are happening asynchronously.

Inside the main function we first obtain a list of all public, non-archived channels. We then filter out all channels that do not match the provided regular expression. Finally, we go through all matching channels and process them.

Next, let's implement `listChannels`. Listing channels can be done via the [conversations.list](https://api.slack.com/methods/conversations.list) API. The code is slightly more complex than simply invoking the respective method via the SDK, because we need to handle [pagination](https://api.slack.com/docs/pagination), in case there are more than a handful of channels.

```js
const listChannels = async (listOptions) => {
  const channels = [];
  let result = await app.client.conversations.list(listOptions);
  result.channels.forEach(c => channels.push(c));
  while (result.response_metadata.next_cursor) {
    console.log(`Fetched ${channels.length} channels so far, but there are more to fetch.`)
    result = await app.client.conversations.list({...listOptions, cursor: result.response_metadata.next_cursor});
    result.channels.forEach(c => channels.push(c));
  }
  return channels;
}
```

Now that we have a list of channels, let's implement `processChannel`. This function will execute the following steps:

1. Join the channel if the bot is not already a member. This is required in order to perform other channel actions later on.
2. Get the last message posted in the channel.
3. If the last message is older than the maximum age, send a message to the channel (if enabled) archive the channel (if enabled).

```js
const processChannel = async (c) => {
  const getLastMessage = async (channelId) => {
    // TODO
  }
  
  const now = Date.now();
  const channelName = `${c.name} (${c.id})`;
  if (c.is_channel) {
    if (!c.is_member) {
      console.log(`Joining channel ${channelName}`);
      await app.client.conversations.join({channel: c.id});
    }

    console.log(`Getting latest message from channel ${channelName}`);
    const lastMessage = getLastMessage(c.id);
    const lastMessageTs = lastMessage.ts * 1000; // we want ms precision
    const lastMessageAge = now - lastMessageTs;

    if (lastMessageAge > lastMessageMaxAge) {
      console.log(`In channel ${channelName}, the last message is ${lastMessageAge}ms old (max age = ${lastMessageMaxAge}ms)`);
      if (sendMessage === 'true') {
        console.log(`Sending message to channel ${channelName}`);
        await app.client.chat.postMessage({
          channel: c.id,
          text: `I am archiving #${c.name} because it has been inactive for a while. Please unarchive the channel and reach out to my owner if this was a mistake!`
        })
      }
      if (archiveChannels === 'true') {
        console.log(`Archiving channel ${channelName}`);
        await app.client.conversations.archive({channel: c.id});
      }
    } else {
      console.log(`Not doing anything with ${channelName}, as there is still recent activity`)
    }
  }
}
```

Joining a channel can be done via [conversations.join](https://api.slack.com/methods/conversations.join). Getting the latest message requires calling [conversations.history](https://api.slack.com/methods/conversations.history), but there is one minor detail we need to handle, so we will implement this in a separate function. Sending a message to a channel can be done via [chat.postMessage](https://api.slack.com/methods/chat.postMessage). Archiving a channel happens via [conversations.archive](https://api.slack.com/methods/conversations.archive).

When the bot joins the channel, Slack will automatically send a join notification to the channel. If we simply obtained the latest message from the channel when running the app for the first time, we would not be able to archive anything, because the bot joined the channel. To solve this problem, yet keep things simple, I decided to simply skip over the latest message if it is of type `channel_join`.

```js
const getLastMessage = async (channelId) => {
  const messages = await app.client.conversations.history({channel: c.id, limit: 2});
  let lastMessage = messages.messages[0];
  if (lastMessage.subtype === 'channel_join' && messages.messages.length > 1) {
    // If the most recent message is someone joining, it might be us, so we look at the last but one message
    lastMessage = messages.messages[1]
  }
  return lastMessage;
}
```

Of course this might have been a real user joining the channel, but if the only activity in a temporary channel is that one person joined, I am still okay with archiving it.

Now with the code being complete, let's build a GitHub Action workflow that will execute it on a daily basis.

## GitHub Action

To set up our GitHub Action workflow, we create a new YAML file in `.github/workflows` with the following content:  

```yaml
name: Run

on:
  schedule:
  - cron: "1 0 * * *"
  workflow_dispatch:

jobs:
  run:
  runs-on: ubuntu-latest

  steps:
    - uses: actions/checkout@v3
    with:
      repository: FRosner/hausmeister
      ref: 6687ed4db20f96441c49c92777c6e2e43a893a3f
    - uses: actions/setup-node@v3
    with:
      node-version: 18
    - run: npm ci
    - env:
      HM_SLACK_BEARER_TOKEN: ${{ secrets.SLACK_BEARER_TOKEN }}
      HM_SLACK_SIGNING_SECRET: ${{ secrets.SLACK_SIGNING_SECRET }}
      HM_CHANNEL_REGEX: "^temp[-_].*"
      HM_LAST_MESSAGE_MAX_AGE: "30d"
      HM_ARCHIVE_CHANNELS: "true"
      HM_SEND_MESSAGE: "true"
    run: node index.js
```

We configure `on.schedule` with the cron expression `1 0 * * *`, which will run the workflow on a daily basis. Thanks to `on.workflow_dispatch` we can also trigger it manually.

The job configuration is fairly simple. First, we check out the Hausmeister repository, then we install Node.js, then install the required dependencies, and finally execute `index.js`. The required credentials can be added as [encrypted secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets).

Once the secrets are created and the workflow definition file is committed and pushed, you can manually trigger a run or wait for the scheduled execution:

![GitHub action execution](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/sge5wmkpq24ewmo24a32.png)

That's it! We built a simple, yet super useful Slack app with a few lines of JavaScript code and GitHub Actions.

## References

- [Slack Etiquette](https://slack.com/blog/collaboration/etiquette-tips-in-slack)
- [Slack Bot Token Documentation](https://api.slack.com/authentication/token-types#bot)
- [Slack API Documentation](https://api.slack.com/apis)
- [Requesting Slack App Scopes](https://api.slack.com/authentication/basics#scopes)
- [Hausmeister GitHub Repository](https://github.com/FRosner/hausmeister)
- [Channitor](https://happybara.gitbook.io/channitor/)
- [The Twelve-Factor App: Config](https://12factor.net/config)

---

Cover image built based on images from [Roman Synkevych](https://unsplash.com/photos/wX2L8L-fGeA) and [Hostreviews.co.uk](https://unsplash.com/photos/aE0iX-bLCJc).