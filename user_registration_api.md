# Building a user registration API

## Context

Dailymotion handles user registrations. To do so, user creates an account and we send a code by email to verify the account.

As a core API developer, you are responsible for building this feature and expose it through API.

## Specifications

You have to manage a user registration and his activation.

The API must support the following use cases:

* Create a user with an email and a password.
* Send an email to the user with a 4 digits code.
* Activate this account with the 4 digits code received. For this step, we consider a `BASIC AUTH` is enough to check if he is the right user.
* The user has only one minute to use this code. After that, an error should be raised.

Design and build this API. You are completely free to propose the architecture you want.

## What do we expect?
* Python language is required.
* We expect to have a level of code quality which could go to production.
* Using frameworks is allowed only for routing, dependency injection, event dispatcher, db connection. FastAPI could be used. Don't use magic (ORM for example)! We want to see **your** implementation.
* Use the DBMS you want (except SQLite).
* Consider the SMTP server as a third party service offering an HTTP API. You can mock the call, use a local SMTP server running in a container, or simply print the 4 digits in console. But do not forget in your implementation that **it is a third party service**.
* Your code should be tested.
* Your application has to run within a docker containers.
* You should provide us the source code (or a link to GitHub)
* You should provide us the instructions to run your code and your tests. We should not install anything except docker/docker-compose to run you project.
* You should provide us an architecture schema.
