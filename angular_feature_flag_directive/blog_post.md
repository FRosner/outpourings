---
title: Implementing and Testing an Angular Feature Flag Directive
published: true
description: How can you implement a directive to conditionally render your components based on feature flags?
tags: angular, testing, javascript, webdev
cover_image: https://dev-to-uploads.s3.amazonaws.com/i/uiq656eb4gwrbwraoxmx.jpg
canonical_url: https://blog.codecentric.de/en/2020/05/implementing-and-testing-an-angular-feature-flag-directive/
---

# Introduction

An important goal of agile software development is to shorten the user feedback loop. To achieve that you want to release your changes as often as possible. This also includes releasing prototypes, e.g. to a smaller audience, gathering customer feedback that can be used to adjust the requirements and priorities accordingly.

Methodologies such as continuous integration and continuous deployment (CI/CD) aim to automate as much of the integration and release process as possible. This way, releasing new software can happen by simply merging a code change into the main branch. Ideally, no manual interaction is needed after to reviewing, approving, and merging a merge request.

When it comes to development workflows, trunk-based development is becoming increasingly popular. Short-lived feature branches help your developers to iterate quickly on new ideas and functionality and reduce the risk of "big-bang" deployments containing massive changes.

In order to be able to merge code and deploy that is not yet ready to be shown to all your customers, you will most likely have to use feature flags. A feature flag is typically a binary value, indicating whether a certain feature is visible in a specific environment. In a very simple setup this can mean that a button or input field is only visible during local development but invisible in production.

In this blog post we want to take a look at how to implement a feature flag directive in Angular such that you can toggle the rendering of certain components as needed. The remainder of the post is structured as follows. First we will discuss different types of feature flags. After that we are going to take a look at an implementation of a structural feature flag directive in Angular together with the respective test. We are closing the post by summarizing our main findings.

# Feature Flag Types

Feature flags can be designed in different ways, ranging from a simple on-off switch, over flags based on environments, all the way to a fully flexible and dynamic setup where your product owner can enable and disable features on-the-fly and also for certain users only.
Which implementation is best for you depends on your use case.

If you have a multi-stage deployment (e.g. development, staging, and production) and you just want to work with short-living branches then having feature flags based on environment variables are probably enough. If your goal is to perform user experiments such as A/B testing, then you might need a more sophisticated solution that involves an external service.

The available types and tools also depend on whether you need to toggle features in the front end, back end, or both. I personally was mainly working on back end code and used feature flags based on environment variables that are passed to the application at runtime. You can then use a configuration library to extract the toggle values and check in a simple `if` statement whether to execute some piece of code or not.

In frameworks that work with the concept of reusable UI components, it is a common use case to hide certain components from the user based on feature flags. In Angular, this can be accomplished by adding a custom directive. Let's take a look at how we can implement and test such a feature flag directive.

# Angular Feature Flag Directive

## Implementation

The goal of the feature flag directive is very similar to the [`ngIf`](https://angular.io/api/common/NgIf) directive: Based on the input decide whether to render a component or not. The difference to a simple `ngIf` is that the feature flag directive has a dependency on the service that knows which features are enabled.

Consequently, the input into the feature flag directive is simply a string indicating the name of the feature we want to condition on. Additionally, we do not have to include the feature flag service dependency in the parent component.

There are multiple tutorials on how to implement a feature flag directive in Angular already (e.g. ["Feature Toggling with Angular and the Angular CLI"](https://medium.com/@amcdnl/feature-toggling-with-angular-and-the-angular-cli-eccf38369b3f) or ["Implementing Feature Flags in an Angular"](https://morioh.com/p/a678b654c472)). The following listing contains my version of the feature flag directive written in TypeScript.

```ts
import {Directive, Input, OnInit, TemplateRef, ViewContainerRef} from '@angular/core';
import {EnvService} from '../services/env.service';

@Directive({
    selector: '[featureFlag]'
})
export class FeatureFlagDirective implements OnInit {
    @Input() featureFlag: string;

    constructor(
        private vcr: ViewContainerRef,
        private tpl: TemplateRef<any>,
        private envService: EnvService
    ) {
    }

    ngOnInit() {
        if (this.envService[this.featureFlag]) {
            this.vcr.createEmbeddedView(this.tpl);
        }
    }

}
```

The job of the directive is to conditionally render the component it is attached to. This can only be achieved by using it as a structural directive (`*featureFlag="'awesomeFeature'"`). Angular will then wrap the component in a template and inject the respective [`TemplateRef`](https://angular.io/api/core/TemplateRef) into the constructor of the directive.

By also injecting the `ViewContainerRef` we can check the feature flag service (e.g. `EnvService`) if the given feature is enabled. Based on the result we create the embedded view in the view container, passing the template reference as an argument.

How you implement the feature flag service is up to you. In our example we are using a mechanism based on environment variables as described in ["How to use environment variables to configure your Angular application without a rebuild"](https://www.jvandemo.com/how-to-use-environment-variables-to-configure-your-angular-application-without-a-rebuild/). Even though I found multiple posts on how to write a feature flag directive, none of them featured how to write tests. So let's look into that next.

## Testing

When testing the feature flag directive there are two test cases we are interested in: Testing that a component with the feature flag directive is

1. rendered if the feature is enabled
2. not rendered if the feature is disabled.

I am using the [shallow-render](https://www.npmjs.com/package/shallow-render) package to render the component and [jasmine](https://jasmine.github.io/) as the testing framework. Shallow render has three advantages over the use of `TestBed` for this test. Firstly, we don't need to create a dummy component class but can instead use a simple `div`. Secondly, we can use the `AppModule` instead of having to configure a testing module. Thirdly, it has built-in support for providing mocks.

The following listing contains the unit test for the feature flag directive.

```ts
import {FeatureFlagDirective} from './feature-flag.directive';
import {EnvService} from '../services/env.service';
import {Shallow} from 'shallow-render';
import {AppModule} from '../app.module';
import {ComponentFixture} from '@angular/core/testing';

describe('FeatureFlagDirective', () => {
    async function renderWith(featureEnabled: boolean): Promise<ComponentFixture<FeatureFlagDirective>> {
        return await new Shallow(FeatureFlagDirective, AppModule)
            .provideMock({provide: EnvService, useValue: {featureActive: featureEnabled}})
            .render(`<div *featureFlag="'featureActive'"></div>`)
            .fixture;
    }

    it('should render the component if the feature is enabled', async () => {
        const fixture = await renderWith(true);
        expect(fixture.nativeElement.querySelector('div')).toBeTruthy();
    });

    it('should not render the component if the feature is disabled', async () => {
        const fixture = await renderWith(false);
        expect(fixture.nativeElement.querySelector('div')).toBeNull();
    });
});
```

The structure of each test is very simple. The first instruction renders the `div` with either the feature flag enabled or disabled. We are relying on a mocked `EnvService` that returns the respective value when queried for the feature status. The second instruction checks whether the `div` has actually been rendered or not.

# Summary

In this post we have seen that feature flags are an important ingredient of agile software development. They enable you to work with short-lived branches, merging to master frequently. Additionally they can be used to dynamically test different feature combinations for different audiences.

In Angular you can use structural directives to annotate components that are supposed to be rendered conditionally based on your feature flags. This works well independently of the way you implement your feature flag service, whether it be based on environment variables or a web service.
We also looked at how to test the feature flag directive using shallow-render and jasmine.

Have you used feature flags before? Did you use or write your own feature flag directive in Angular? If you have a more powerful implementation, please feel free to share some details as well as the use case for it. I'm curious!
