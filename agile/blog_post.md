---
title: Explain Agile Like I'm a Sports Student
published: false
description:
tags: agile, explainlikeimfive
cover_image: ???
---

## Agility In The Wild

During my professional career I encountered many people and teams who either claimed to be agile or were trying to become agile. When you ask them about their motivation you get the same answers mostly:

- Customer orientation
- Doing things quicker with less managerial overhead
- Planning ahead is not useful
- Competition is doing agile

While their intentions are noble, the reality looks different in many cases:

- Unclear prioritization of customer requests
- People working on random things
- Managers giving tasks directly to individuals leading to unevenly distributed workloads
- No time estimation possible

Of course there are also many teams who are getting it right. And continuous improvement is part of the process. In this blog post, however, I would like to discuss agile from the ground up. I want to derive a formal definition and link the existing methods and techniques to this definition to show why they are effective.

The post is structured as follows: In the next section we are going to discuss a formal definition of agile. Afterwards we will take a look at how different techniques and methods affect your agility. We are closing the blog post by discussing the learnings.

## Defining Agility

When trying to define agile, many people associate agility with speed. They say that being more agile means doing things quicker. When defining agile, I like to take a look at the definition of _agility_ from sports science:

> _"Agility is the ability to change the direction of the body in an efficient and effective manner."_ - [Wikipedia](https://en.wikipedia.org/wiki/Agility)

Achieving this requires a combination of

- **Balance.** The ability to maintain equilibrium when stationary or moving (i.e. not to fall over) through the coordinated actions of our sensory functions (eyes, ears and the proprioceptive organs in our joints).
- **Speed.** The ability to move all or part of the body quickly.
- **Strength.** The ability of a muscle or muscle group to overcome a resistance.
- **Coordination.** The ability to control the movement of the body in co-operation with the body's sensory functions.

We can now try to adapt this definition from the body to an organization. We are going to focus on a single team for now, as it is easier to reason about.

> _Agility is the ability of a team to change the direction of the development in an efficient and effective manner._

Achieving this requires a combination of

- **Balance.** Being able to shift the development effort in any direction.
- **Speed.** The ability to execute individual tasks quickly.
- **Strength.** The ability to execute difficult tasks.
- **Coordination.** The ability to coordinate within the team, and with the different stakeholders and customers.

The question is, how to build a team that has the balance, speed, strength, and coordination it requires?

## Becoming Agile

When reading about agile, you will certainly stumble upon different frameworks and techniques. The [agile manifesto](http://agilemanifesto.org/) is a joint effort by many well-known developers to write down [principles for agile software development](http://agilemanifesto.org/principles.html).

When using an agile framework like [Scrum](https://en.wikipedia.org/wiki/Scrum_(software_development)), you get many techniques out of the box. It is not necessary to follow the rules by the book but the concepts are there for a reason and it makes sense to understand them. I don't want to bore you with too many details about Scrum and you are free to read more about it if you are interested.

The basic concept about Scrum is to have cross-functional, self-organizing teams working as autonomous units to reach a common goal. But what is it that makes a Scrum team agile? How do your processes and rules affect balance, speed, strength, and coordination? What is the role of the team composition and the individual people?

### Balance

![Balance](https://thepracticaldev.s3.amazonaws.com/i/th435kqg58mcfdzda180.png)

You need balance in order to shift the development effort in any direction. If your most important customer asks for a feature, this feature gets prioritized, you should be able to work on it even if you worked on something completely different before.

A Scrum team should be cross-functional. It needs to have all the required skills to work towards the vision / goal. Having [T-shaped individuals](https://en.wikipedia.org/wiki/T-shaped_skills), a.k.a. generalizing specialists, allows you to shift focus and start any new feature without external dependencies. Include code review or pair programming into your development process to ensure knowledge transfer.

Introducing work in progress limits allows to start something new without having to finish _x_ different tasks first. While this reduces productivity a bit, it decreases the average in progress time of your tickets.

Team members should have enough slack time to foster creativity. Giving room for personal development is key for finding the right balance between daily work and innovation. Workloads should be predictable, equally distributed among team members and across time. Having someone working their ass off looks great until they have a mental breakdown.

Write automated tests and do regular refactorings. Having maintainable code helps to keep your balance. It allows you to stop working on a topic and then get back to it half a year later. People will have more confidence in the code and are encouraged to make changes without the fear of breaking something.

### Speed

![Speed](https://thepracticaldev.s3.amazonaws.com/i/yhdz26kz4ftg8osynjm2.png)

In order to finish the development of individual tasks quickly it is important for your developers to focus. They should be working only on well-defined, concise tasks with a clear scope.

If your developers have to switch the context a lot, this overhead will reduce their ability to finish one task in due time. Introducing work in progress limits helps also here. You should communicate and resolve blockers as soon as possible. This is where the Scrum master has to support.

If the tasks are not well-defined and there is a lot of clarification needed after starting to work in it, developers will be busy asking questions instead of developing. Take enough time to refine your tickets and make sure every developer understands the problem before marking the ticket as ready to be worked on. If a ticket is too complex, break it up into smaller tasks.

### Strength

![Strength](https://thepracticaldev.s3.amazonaws.com/i/q52i7vue3rrj3jb3vvmf.png)

Building software is hard. Building anything is hard, actually, when you are trying to get it right. When dealing with difficult tasks you need the right people.

Identify the skill set required for your product and get experts in the respective fields. Trust in the expert opinion, empower them, and give them the right tools to get their job done. You wouldn't tell someone to build a tunnel and give them only a shovel.

### Coordination

![Coordination](https://thepracticaldev.s3.amazonaws.com/i/6cjnnq1auoh6ir2l7fu1.png)

Being fast and strong is very important. If you cannot coordinate your movements, however, you will most likely end up wasting energy or even crashing.

In Scrum, coordination inside the team is ensured by a well-defined development process. There need to be written definitions of ready (When is a ticket ready to be worked on?) and done (When is a ticket finished?). There should be working agreements stating the shared values of the team. The Scrum master is supporting in process related questions.

Coordination and prioritization of customers requests is done by the product owner. His or her role is to collect requirements and feedback from the different stakeholders, prioritize them based on the importance for the product, and discuss them with the team if they need to be made ready for development.

The interface between the development team and the customers is well defined. Direct touch points only exist in defined meetings. There should be no ad-hoc requests coming directly to the development team. The product owner is protecting the development team from distractions coming from external stakeholders during the sprint.

## Discussion

Looking at agility from this angle instead of just treating it as doing things fast has some interesting implications. Although speed is one important ingredient in agile methodologies, it is about finding the right combination of speed, strength, balance, and coordination in order to be successful.

Rather than constantly running at the same pace, in Scrum you alternate between phases of focus (development sprint), and periods where you take your time to reflect and reprioritize (sprint review, backlog refinement, retrospective). Sometimes it is even more useful to slow down a bit in order not to miss the turn at the next intersection.

Keep in mind that it is not only about doing the right things (where to run towards) but also doing the things right (which path to take). By constantly refactoring, adding automated tests, having code reviews and pair programming, you make sure not to choose a path which gets you stuck with no return.

When starting to apply agile methodologies you will face frustration. Sometimes things look slow and you would rather start another ticket instead of unblocking or pair programming on an important issue. Although your productivity looks reduced and you might end up with less features than before, the chances are high that these features are exactly what the customer wanted and your process becomes more customer focused.

Do you agree with my definition of agility? Did you go through an agile transformation, already? How did it go? Please let me know in the comments what you think!
