---
title: Frank - How are you so productive?
published: true
description: This blog post explores various strategies to enhance productivity as a software engineer, focusing on balancing effectiveness and efficiency.
tags: productivity, learning, career
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/f8mslk0no0wc08bo8qju.jpg
---

## Introduction

Friends and colleagues often ask me: "Frank - How are you so productive?". While I don't have a silver bullet, I developed a mindset and adopted a set of tools and techniques that help me to be productive as a software engineer. In this post, I will share some of these strategies with you.

## What is Productivity?

In economics, productivity measures the ratio of outputs and inputs. In software engineering, I consider output to be the value created by my work and inputs to be the money spent, which includes my work time, as well as any fees for the tools I am using to produce the value. In my opinion, it is important to consider value of your work as output, not pull requests merged or tickets closed.

When we talk about productivity, we often view it as a combination of effectiveness and efficiency.

- Increasing effectiveness is about increasing output while keeping the input constant. In the context of output being value produced, it is often paraphrased as "doing the right things".
- Increasing efficiency is about decreasing input while keeping the output constant. It is often paraphrased as "doing things right".

This distinction is useful because it can help identify potential for improvement. Consider being very fast in coding up something that is not needed. This is high efficiency but low effectiveness. On the other hand, consider writing some very valuable feature in a programming language you have no experience in, which is slowing you down significantly. While being highly effective, the efficiency will be low.

## Prioritization

Being effective means "doing the right thing". But how do you identify what the right thing is? You will need to identify the needs. This can be done by talking to customers and stakeholders, reading customer feedback, or analyzing business metrics. Once you have identified the relevant goals / epics / features / tasks, you can prioritize them.

When prioritizing with productivity in mind, we cannot just consider the impact (output). We also need to consider the required effort (input). A useful tool for prioritization is the impact-effort-matrix.

![import effort matrix](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/o30m8i3w2fs1b8epn121.png)

You place your tasks on the plane between the effort and impact axes. To maximize productivity, focus on quick-wins first. Then plan to tackle the major projects, adding fillers here and there. Avoid waste.

## Executing and Building Momentum

By prioritizing high-impact, low-effort tasks, you have a good foundation for productivity within your system (company, department, team). When looking at time and effort spent by individual contributors, e.g. yourself, however, there is a lot of potential for improvement, too. Having the "perfect plan" is not enough if you are not able to execute efficiently.

Everyone has the same amount of time available to them. For the sake of this argument, let's assume you are spending 8 hours per day at work. However, you will not be able to work the entire 8 hours on high-impact tasks. There are meetings, operational tasks, overhead, and distractions. And even when you are working on your task, your efficiency can depend on your mood, your energy level, and your ability to focus.

Personally, my biggest factor for long term productivity is building and maintaining momentum. I like to use a snowball analogy to reason about my momentum at work. In physics, momentum is defined as the mass of an object multiplied by its velocity.

When you start a new job, or move to a new role, you start off as a small snowball on the top of a hill. The mass of the snowball corresponds to the knowledge and skills you accumulate. The velocity corresponds to the rate at which you are able to complete tasks like coding, reviewing PRs, and so on.

When you start pushing for the first time, it feels hard to gain momentum as the ball is very small, and gets stuck easily on small branches or stones. As you keep going, the ball gains size and speed.

![snowball going downhill](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/29ria77me3l61mp69a6f.png)

In order to build and maintain your momentum over time, you have several responsibilities:

* **Increase** your snowball's **mass**. Lean new programming languages, frameworks, tools, and technologies. Get familiar with new code bases, and understand the business domain you are working in. Improve your tooling and workflows. Build lasting relationships with your co-workers, stakeholders and customers. All of this will allow you to overcome obstacles more easily.
* **Plan** ahead to avoid hitting major obstacles like trees that risk stopping your snowball, or even making parts of it fall off. This means identifying potential blockers and risks early, and either avoiding them or mitigating them before you reach them.
* **Keep pushing** your snowball. This means making progress on your tasks, delivering value. You need to find the right amount of pushing, as pushing too hard will make it hard to stop and navigate around obstacles or changing priorities.

How do you balance these activities throughout your work day / week? If you focus only on pushing, without planning, you'll easily run into obstacles. If you are not working on gaining mass, you'll not be able to overcome growing obstacles and take on bigger challenges. If you are only working on gaining mass but not pushing, you are not delivering value.

Over the course of my career, applying the core principles of Agile Software Development has worked well. Additionally, I discovered and honed some techniques and tools that help me build and maintain momentum every day. The following sections will do a quick recap of the agile principles and then dive into the tools and techniques I use.

## Agile Software Development Principles

I am a big fan of the principles behind the [Manifesto for Agile Software Development](https://agilemanifesto.org/principles.html). And I'm not talking about "Agile Methodologies" like Scrum, but the core principles. To summarize the most important ones for me:

- Delivering value to the customer continuously
- Welcoming changing requirements
- Simplicity - maximize the amount of work not done
- Continuous attention to technical excellence and good design
- Regular reflection and adaptation

How do I apply these in my daily work? I only consider something done, if the work is usable in production. I break down tasks into the smallest possible pieces, aiming to finish pull requests within a day to get early feedback and iterate quickly. If priorities change, this allows me to switch to another task without leaving half-finished work.

This ensures that my work is focused on adding value, and I can adapt to changing requirements quickly. To ensure simplicity, I apply the YAGNI (you ain't gonna need it) principle. I only implement what is needed now, and avoid over-engineering. I design explicitly to avoid losing momentum when having design discussions after the code is written. When revisiting code, I always try to improve it, paying back technical dept continuously.

I also regularly reflect on my work, and try to improve my workflows and tools. We will talk more about that in the Kaizen section below. If you want to know more about Agile Software Development, checkout my post [Explain Agile Like I'm a Sports Student](https://dev.to/frosnerd/explain-agile-like-im-a-sports-student-3m8l).

Next, let's dive into some concrete tools and techniques that you can try out yourself.

## Tools and Techniques

### Kaizen

![Kaizen](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/0xm4pefep7fg828862ze.png)

Kaizen is a Japanese term that means "continuous improvement". It is a philosophy that focuses on making small, incremental changes to processes, workflows, and tools. It was popularized as part of the [Toyota Way](https://en.wikipedia.org/wiki/The_Toyota_Way). The core ideas are:

- Improvement is a never-ending process. Make small, consistent changes to achieve significant, long-term results.
- Empower everyone to identify inefficiencies and suggest solutions.
- Focus on the process, not the people. Improve processes systematically.
- Eliminate waste. Activities that do not add value to the customer or organization need to be removed.
- Measure and reflect. Use metrics to track progress, experiment with changes, and reflect on the results.

I apply Kaizen in the teams I work with, but also on a personal level. At the end of each day, I spend 5-10 minutes to reflect on the activities I performed that day, and the impact they had on the customer or my organization. I block 30-60 minutes every week to improve my workflows / tools.

Examples are:

- Automate creation of daily or weekly messages / reports I compiled manually before.
- Improve my coding efficiency by learning or reviewing keyboard shortcuts, IDE features or plugins.
- Cancel meetings that have a low return of time invested (ROTI). Consider reading the meeting summary / minutes instead.
- Add new folder and rule in my inbox to funnel some low-priority messages that I can look at on a weekly basis.
- Archive some old Slack channels that are not relevant anymore.

### Zero-Inbox

![overflowing mailbox](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/6viorqjyp6acrszouwwf.png)

The zero-inbox technique aims at managing your inboxes (email, slack) effectively by keeping the number of unread messages at (or close to) 0. The goal is to reduce cognitive burden of a cluttered inbox, and to ensure that you are not missing important messages. The core ideas are:

- Process every message, don't just "check" it. Apply the 4 D's: Delete, Delegate, Defer, Do.
  - **Delete** the message (mostly applies to emails) if it is irrelevant, spam, or unnecessary.
  - **Delegate** the task if it belongs to someone else. Forward it immediately.
  - **Defer** the message if it requires your action but cannot be handled immediately. Schedule it for a later time. Most email clients have this functionality, and for Slack channels, I use the "remind me about this" feature.
  - **Do** the task immediately if it takes less than two minutes to complete.
- Use folders, labels, channels to categorize messages. Use automated filters / rules to organize the incoming messages automatically before you process them. I personally have different folders in my email account, based on the projects and the type of message, e.g. pull requests, ticket updates.
- Don't use email as a To-Do list. Move larger, actionable items to a dedicated task management tool.
- Block message time. Don't check emails or Slack continuously throughout the day, but use dedicated time slots, ideally when you're least productive, e.g. after lunch or in the afternoon.
- Unsubscribe and filter. If you receive newsletters / updates that are not relevant, unsubscribe. If you cannot unsubscribe, add an automated filter to delete the messages before they reach your inbox.
- Archive aggressively. I personally don't archive emails, but I use a filter to show only unread messages in my inbox. I archive orphaned temporary Slack channels aggressively.
- Keep it simple and consistent. Whatever system you use, it needs to be easy enough for you to apply on a daily basis.

### To-Do Lists

![todo list](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/k0utich8a7bpt5qngbtx.jpg)

I tried using digital To-Do lists, but they didn't work out for me. They often got outdated, or some tasks got stuck on there forever. I switched to using a notebook, which lies in front of me on my desk. I use a simple system:

- Every day, I write down the date and the tasks I want to complete that day, in order of priority. I either do it in the evening of the previous day, or as the first thing in the morning.
- I check off tasks as I complete them. Whenever I engage in an activity, e.g. looking at a Slack message or an incoming PR review request, I review my list to remind myself what the most important task is. That helps me to get back on track, and focus on the most important bits first.
- It is okay to add new tasks to the list as the day goes on. It is okay to not finish all the tasks. However, in the spirit of Kaizen, I will review these occasions at the end of the day, coming up with a plan to avoid them in the future.

Let's take a look at an example list:

![my to do list](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/e2tn5l16jdn173i0kdf8.jpg)

Imagine that while working on the blog post, a colleague pings you that you need to send in a report by today. You add it to the top of the list, and start working on it immediately. At the end of the day, you did not manage to check your emails.

When closing your day, you attempt to understand how it happened that the report showed up surprisingly. There are different possible reasons, such as:

1. The report needed to be finished today, you knew about it, but forgot when you planned your day. In that case, you might want to adjust your process to include a reminder of due tasks one day before the due date.
2. The report needed to be finished today, but you didn't know about it because your colleague forgot to tell you. In that case, communicate clearly how much time you need in advance. Consider using a shared task management tool, where your colleague can assign you to certain tasks, that will notify you about this.
3. The report didn't have to be finished today. It wasn't going to be sent by end of next week anyway. In that case, make sure to challenge the priorities of urgent ad-hoc tasks in the future.

### Time Boxing and Time Blocking

![Calendar](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/wtfdfhib6gyn53u3pnf2.jpg)

I use time boxing and time blocking daily. Time blocking helps me in planning my day and week, ensuring I make room for important, short- and long-term activities. Time boxing helps me to avoid getting stuck or lost in details.

Here are some activities I block time for:

- Reviewing pull requests (daily)
- Writing code (daily)
- Reading and answering messages (daily)
- 1on1 / team meetings (weekly / bi-weekly)
- Education, learning, personal development (weekly)
- Workout (daily)

I sometimes use my calendar to block the time, or I'm writing the times next to the items on my To-Do list. I apply time-boxing within each block, but also on a broader scale. For example, when I timebox my PR reviews to 60 minutes, I will stop after 60 minutes even if I did not review all PRs. The remaining ones will get a higher priority the next day.

Time boxing also helps me to manage unknown unknowns better. When starting a bigger task, I often kick it off with a proof of concept (POC), time-boxed to a few hours. If I am not able to complete the POC in that time, I change the estimation of the effort needed for the task, placing it on another spot in the impact-effort-matrix, reprioritizing it accordingly. If it is still top priority, I'll extend the time box but if there are other quick-wins available, I might switch to them for now.

Time blocking helps me keep a balance of the different activities needed to build and maintain momentum, while time boxing emphasizes progress over perfection.

### Focus and Pomodoro

![camera lens focusing](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/c04zgqlmioday8fgk3fs.jpg)

Our brains are capable to solve complex problems, but struggle to deal with distractions and context switching. I personally have found that my productivity over 8 hours is higher if I dedicate 4 hours to deep work, with no distractions, and 4 hours of shallow work, where I can handle interruptions, compared to 8 hours of mixed work.

To successfully enter deep work, I need to have the right environment. I use headphones with music on, and my desk needs to have a little bit of clutter on it, but not too much. If there's too much, I have to clean it first. I might also turn off messaging programs / notifications.

While deep work is incredibly effective, it is also exhausting. My ability to focus drops rapidly after ~45-60 minutes, but after 30 minutes the focus starts to take a toll on my body. My head starts to hurt, and my muscles start to tense up.

To help maintain a balance between work and recovery, I often use the [Pomodoro technique™](https://www.pomodorotechnique.com/). The core idea is to work for 25 minutes, then take a 5-minute break. After 4 Pomodoros, take a longer break of 15-30 minutes. 

Pomodoro has another positive effect on my work. It forces me to split my work in smaller chunks, which can be completed within a single slot. E.g. if I'm writing code, my goal is to have it compile after each slot. Ideally, I'll also be able to commit the changes. When writing a blog post, I aim to complete a section within a slot.

### Pareto Principle (aka 80/20)

![laptop with diagrams and charts](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/f2px7rq217tqacmn1onj.jpg)

The idea behind the Pareto Principle is that 80% of the consequences come from 20% of the causes. When applied to work, it means that 80% of the value comes from 20% of the work. We can make use of that principle to maximize productivity by focusing on the 20% of the work that brings the most value.

What does that mean in practice for me?

- Use GenAI extensively. I use GenAI to generate code, which is often times not great, but if it works, it'll do as a first iteration. I use GenAI to generate automated tests as well. I would rather have ugly, tested code, than beautiful, refined, high performance code without any tests. Don't aim for 100% code coverage in the beginning, but focus on the key aspects.
- Don't over-engineer. First, make it work, later make it right (if it has proven its value).
- Refactor constantly. Whenever I touch code I look for opportunities to improve it. That mechanism ensures that throw-away code is not over-engineered, but relevant code converges to a high quality.
- Reduce toil progressively. When you do something once, it's worth writing it down in some note or ticket. When you do it on a regular basis, but not very often, create a runbook. When the runbook becomes long and you run it more often, script it up. When you run the script often, automate it.

Of course, you need to keep in mind that the remaining 20% of results, taking up 4 times as much of your time as the first 80% to finish, is dept you are paying interest on. So you should choose wisely how much dept you can take on, how much interest you are willing to pay, and invest time in paying back dept regularly.

So why is applying this technique saving time? If you end up doing all the work eventually, what's the point? The point is the work you are doing is almost never going to solve the problem 100%. It may be because you did not understand the problem entirely. Or maybe the problem changes over time. Maybe or some other, better solution comes into the mix later down the line. By focusing on the 20% that brings the most value, you are able to deliver value faster, and you are able to pivot more easily.

### Gemba Walking

![car factory assembly line](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/lz7fkqn4h3g7prog6ds5.jpg)

Gemba walking is yet another technique coming from the Toyota Way. Gemba is a Japanese term that means "the real place". In the context of software development, it means going to the place where the work is done, e.g. the team's workspace, the code repository, the CI/CD pipeline, the incident channels, the production environment. This is relevant for me as a tech lead to avoid the "ivory tower" syndrome, and to stay connected to the work my colleagues are doing.

Gemba walking helps me to identify inefficiencies, bottlenecks, and blockers early. It also helps me to understand the context of the work better, and to build relationships with my colleagues. I try to do Gemba walks every day, blocking ~15 minutes for it. The key ideas are:

- Go where value is created. In SRE, I call this "the trenches".
- Observe, don't judge. Ask questions and listen to the problems your colleagues are facing. Read between the lines, be curious.
- Engage with colleagues.
- Focus on processes, not people.

### Escalation

![frustrated person](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/bm7kezvs161vcyfy4wo7.jpg)

Escalation involves raising an issue to higher authority or expertise levels when it cannot be resolved at the current level. Escalating quickly is important to ensure efficient resolution of issues by ensuring they are handled by the people with the right expertise, authority, or resources.

Escalation is also important to avoid getting stuck / blocked on a task. While it might seem like "complaining" to some, it is in the interest of the company and your customers to resolve issues quickly.

I often combine escalation with time-boxing. If I do not manage to complete a task in the estimated time, I can escalate it to the respective parties, e.g. my boss, or an expert in the field.

# Summary and Conclusion

In this post we explored various strategies to increase productivity as a software engineer, while balancing effectiveness and efficiency. We highlighted the significance of prioritization using the impact-effort matrix to focus on high-impact, low-effort tasks. 

We saw how to build and maintain momentum, peeking into a productivity toolset, including Agile principles to ensure value delivery and adaptability, Kaizen for continuous improvement, zero-inbox techniques for managing messages, the use of to-do lists for daily task management, time boxing and time blocking for effective time management, the Pomodoro technique for maintaining focus, the Pareto Principle for maximizing value, Gemba walking to stay connected with the team's work, and the importance of quick escalation to resolve issues efficiently.

What are your favorite productivity tools and techniques? How do you balance effectiveness and efficiency in your work? Please hare your thoughts in the comments!

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).

---

- Cover photo by <a href="https://unsplash.com/@leafybirdy?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">kris</a> on <a href="https://unsplash.com/photos/selective-focus-photography-of-productivity-printed-book-n9u9ZEoH2yM?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- To-Do list photo by <a href="https://unsplash.com/@thomasbormans?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Thomas Bormans</a> on <a href="https://unsplash.com/photos/a-notepad-with-a-pen-on-top-of-it-pcpsVsyFp_s?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- Calendar photo by <a href="https://unsplash.com/@erothermel?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Eric Rothermel</a> on <a href="https://unsplash.com/photos/white-printer-paperr-FoKO4DpXamQ?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- Kanban photo by <a href="https://unsplash.com/@parabol?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Parabol | The Agile Meeting Tool</a> on <a href="https://unsplash.com/photos/a-woman-writing-on-a-wall-with-sticky-notes-FLsPtPiE4zU?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- Frustrated person photo by <a href="https://unsplash.com/@gunaivi?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">ahmad gunnaivi</a> on <a href="https://unsplash.com/photos/man-in-bluee-ssweater-OupUvbC_TEY?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- Camera lense photo by <a href="https://unsplash.com/@pawelskor?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Paul Skorupskas</a> on <a href="https://unsplash.com/photos/person-holding-camera-lens-7KLa-xLbSXA?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- Laptop photo by <a href="https://unsplash.com/@goumbik?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Lukas Blazek</a> on <a href="https://unsplash.com/photos/turned-on-black-and-grey-laptop-computer-mcSDtbWXUZU?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
- Car factory photo by <a href="https://unsplash.com/@satterfieldgroup?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Michael Satterfield</a> on <a href="https://unsplash.com/photos/a-row-of-cars-parked-in-a-parking-lot-vnTzjMW9OoM?utm_content=creditCopyText&utm_medium=referral&utm_source=unsplash">Unsplash</a>
