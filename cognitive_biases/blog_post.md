---
title: Ten Cognitive Biases to Look Out For as a Developer
published: true
description: Cognitive biases can be viewed as bugs in our thinking. In this blog post we want to take a look at ten cognitive biases to look out for as a developer.
tags: beginners, discuss, psychology, career
cover_image: https://thepracticaldev.s3.amazonaws.com/i/uoq6e8acyekr5i9p48h5.jpg
canonical_url: https://blog.codecentric.de/en/2019/05/ten-cognitive-biases-to-look-out-for-as-a-developer/
---

# Introduction

Cognitive biases can be viewed as bugs in our thinking when collecting, processing, and interpreting information. From an evolutionary stand point they are features rather than bugs as they often enable us to be happy, social, and thus to survive. Nevertheless, biases can become an obstacle when it comes to logical reasoning. This is especially the case for professions like engineering or science.

In this blog post we want to take a look at ten cognitive biases to look out for as a developer: The shared information bias, the social desirability bias, the confirmation bias, motivated cognition, the sunk cost fallacy, the in-group bias, the halo effect, the attentional bias, the false consensus effect, and the bias blind spot. Each section briefly explains the bias, what impact it can have on you in your daily development work, and what you can do to avoid the negative effects.

# The Biases

## Shared Information Bias

The shared information bias [1] is known as the tendency of a group to discuss things that many people are familiar with instead of talking about the ones only few people know. This might influence decision making in a negative way if crucial information is available only to few members of the group. It can also impact knowledge sharing if topics become too general.

One way to decrease the effect of the shared information bias is having longer meetings without time pressure [2]. However as a developer I would like to have short, focused meetings. Instead, you can identify relevant expertise before the meeting, invite those experts [3], and moderate the discussion in a way to account for that [4].

## Social Desirability Bias

The social desirability bias [5] describes the tendency to communicate in a way that will be well received by others, even if it does not represent your opinion or the truth. A common example is that people are unlikely to answer truthfully in a survey when asked whether they are doing drugs or masturbating, for example.

While this bias might benefit survival because it enables us to live in groups, it can hinder knowledge discovery and finding the right solution to your problem. As a developer this might impact the way you are taking decisions. Maybe it feels right to add another test case but your team is not fond of TDD so you might not try to convince them and just drop the test.

In my opinion it is important to create a working environment where you can communicate your opinions without the fear of getting socially isolated. Moderating difficult discussions can help in this case.

## Confirmation Bias

Confirmation bias [6] is the tendency to look for evidence or interpret your observations in a way that confirms your previous beliefs or biases. There are three forms of this bias:

- **Biased search.** When looking for information or facts you are most likely looking for something that will support your current hypothesis. For me this sometimes impacts the way I debug code. I see an error message and I have an idea where it could be originated from. Obviously I start there and that's not a bad thing to do. What is important in my opinion, is to keep this bias in mind if you get stuck and maybe take a step back.
- **Biased interpretation.** After you found some information you are more likely to interpret it in a way that supports your beliefs. When comparing different technologies you can try to avoid biased interpretation by involving people with different beliefs and backgrounds into the discussions.
- **Biased memory.** Biased memory describes that even if you managed to search and interpret information in a neutral manner, you are still likely to remember only the parts that reinforces your expectations. Generally it is good to document your decisions so you can read them later, refreshing your memory in an unbiased way. [Architecture Decision Records](http://thinkrelevance.com/blog/2011/11/15/documenting-architecture-decisions) are a lean, yet effective way to document architecture decisions and avoid selective memory when you are revisiting those decisions later on.

## Motivated Cognition

Motivated cognition refers to motives influencing your way of thinking, reasoning, and decision making [7]. A common example is wishful thinking, which is the reason why lotteries are so popular although your expected outcome is negative. It is also useful however, because it gives you hope in hopeless situations and protects you from too many negative thoughts which might lead to mental health issues.

As a developer, motivated cognition might impact you in different ways. Motivational factors might cause you to accept responsibility only in positive cases but not in case of failure. You might also consider yourself to be above average in a particular skill because you define the skill based on your personal strengths.

To avoid motivated cognition having a negative impact on your work, it can help to take an outside view into account. For me I like to talk to close friends because I know that they are honest with me. If they have different motives than you they can help you to see the problem from a different angle at least.

## Sunk Cost Fallacy

The sunk cost fallacy is also known as throwing good money after bad. It is very prominent in our daily lives both in the personal and public sector. People tend to become irrational after they invested a significant amount of time, effort, or money into a solution.

If a long lasting relationship is doomed we might hold on to it although both parties would be happier separately. If an airport is being built for such a long time without success and it would be cheaper to start fresh we still try to finish it.

In software projects there are two levels where the sunk cost fallacy might happen. On a project level, useless projects do not get canceled early because "we invested so much already". Software gets finished where it is clear that nobody is going to use it, just because it is almost done. On a developer level you might not be willing to replace your custom code by a newly discovered library that does the job in a better way because you spent a lot of time writing that code.

## In-Group Bias

The in-group bias [8] is something we can experience quite early in hour lives, e.g. in school. If you don't belong to the group, you are not cool or respected. Again, this behaviour has its roots in our tendency to form groups in order to survive.

But how can the in-group bias impact you as a professional? The most common manifestation is that you view your own profession as superior. I witnessed back-end developers claiming that front-end developers are not real developers. Machine learning experts claiming that they are better than statisticians, physicists claiming that philosophy is useless.

I believe there is great value in different view points and ideas when attempting to solve a problem. Having a team of mixed professions can yield more robust and better solutions and you should avoid in-group thinking as much as possible. This goes both for professions and skills, as well as across teams.

## Halo Effect

The halo effect is a cognitive bias where your assessment of someone or something is not based on related, vague information but instead on unrelated, concrete information [12]. A common example is when we assume that a good looking, nicely dressed person is also a good in a moral sense, although those two things are unrelated.

In our industry I typically encounter the halo effect in two ways: If an expert claims something outside of his or her expertise people tend to believe it nevertheless. If big companies like Google publish a paper or software, many people immediately use it, copy it, or recommend it, just because it's from Google. But remember the saying: All that is from Google is not gold.

There is also a negative version of the halo effect. We often judge a book by its cover, although physical attractiveness has nothing to do with professional skills (unless partly for models of course). When reviewing an application in a company, or a paper submission for a journal, blind reviews can reduce that risk.

## Attentional Bias

Attentional bias in decision making [13] describes the tendency towards weighting observations and facts higher if they are in the focus of our attention for a longer time. This means if you keep hearing something you might believe it is true at some point.

While I believe that getting supporting facts from different sources is an indicator that those facts are true, you need to be aware that this only holds if those sources are truly independent. In many cases we are inside a community or filter bubble (consider Twitter, e.g.), where the same arguments and facts are repeated over and over again without adding any new information or view point.

In my life I encountered a few statements that remained unquestioned just because so many people said them. One of them is that the JVM is slow (What does that even mean? When and compared to what?). Another one is that vaccination causes autism, which is not proven and the paper that indicated this was found to be wrong. Please vaccinate your kids!

## False Consensus Effect

The false consensus effect [9] is a tendency to overestimate the extend to which others agree with your opinion or think the same way that you do. It is called false consensus because if every person within a group thinks that way, there is a sense of consensus although in reality there is none.

Ignoring this bias when working in a team might cost you at a later stage of the project. Decisions are taken without discussion, because the person taking the decision believes that it's clear to everyone anyway that this is the right call. You can avoid the false consensus effect by writing down decisions very precisely and presenting them to the team. Usually you will reveal the false consensus once things are written down and discussed based on that.

## Bias Blind Spot

Last but not least the meta bias: the bias blind spot. While recognizing the impact of biases in others you fail to see the impact of biases in your own judgement [10]. One should note that the susceptibility to the blind spot is not related to decision making ability [11]. The majority of the people seem to think that they are less biased than others.

The good news is that by reading this post you already made a step towards recognizing your biases and might avoid the blind spot in some occasions.

# Discussion

In this post we looked at ten biases that might impact your life as a developer. Being aware of potential issues is a prerequisite to systematically preventing them. Do you know another bias I did not mention that might impact the work of a developer?

Think about your work, meetings or discussions you had, decisions you have taken - were you biased? If your answer is no, please read the section about the bias blind spot again. If your answer is yes, please share your story in the comments!

# References

- [1] Forsyth, Donelson R. "Group dynamics." Cengage Learning, 2018.
- [2] Kelly, Janice R., and Steven J. Karau. "Group decision making: The effects of initial preferences and time pressure." Personality and Social Psychology Bulletin 25.11 (1999): 1342-1354.
- [3] Wittenbaum, Gwen M. "Information sampling in decision-making groups: The impact of members' task-relevant status." Small Group Research 29.1 (1998): 57-84.
- [4] Stewart, Dennis D., and Garold Stasser. "Expert role assignment and information sampling during collective recall and decision making." Journal of personality and social psychology 69.4 (1995): 619.
- [5] Edwards, Allen L. "The social desirability variable in personality assessment and research." (1957).
- [6] Plous, Scott "The Psychology of Judgment and Decision Making", p. 233 (1993)
- [7] Dunning, David. "A newer look: Motivated social cognition and the schematic representation of social concepts." Psychological Inquiry 10.1 (1999): 1-11.
- [8] Efferson, Charles, Rafael Lalive, and Ernst Fehr. "The coevolution of cultural groups and ingroup favoritism." Science 321.5897 (2008): 1844-1849.
- [9] Perloff, Linda S., and Philip Brickman. "False consensus and false uniqueness: Biases in perceptions of similarity." Academic Psychology Bulletin (1982).
- [10] Pronin, Emily, Daniel Y. Lin, and Lee Ross. "The bias blind spot: Perceptions of bias in self versus others." Personality and Social Psychology Bulletin 28.3 (2002): 369-381.
- [11] Scopelliti, Irene, et al. "Bias blind spot: Structure, measurement, and consequences." Management Science 61.10 (2015): 2468-2486.
- [12] Lachman, Sheldon J., and Alan R. Bass. "A direct study of halo effect." The journal of psychology 119.6 (1985): 535-540.
- [13] Nisbett, Richard E., and Lee Ross. "Human inference: Strategies and shortcomings of social judgment." (1980).

---

Cover image created by [Dean Hochman](https://flic.kr/p/ot7ktg)
