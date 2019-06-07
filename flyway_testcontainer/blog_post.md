---
title: Testing Your Database Migrations With Flyway and Testcontainers
published: true
description: Automated database migrations are an important building block of agile software development. How can we perform migrations and how do we test them?
tags: kotlin, databases, testing, sql
cover_image: https://thepracticaldev.s3.amazonaws.com/i/ks56rv99m9lcw1nleh03.jpg
---

# Why Database Migrations?

*Database migrations* are usually a combination of schema and data migrations in databases. A *schema migration* denotes a change in an existing database schema, e.g. adding a column or creating a new index. A *data migration* involves changing existing data in a database, e.g. by normalizing the representation of missing values in a column, such as the conversion of `null`, `""`, and `"EMPTY"` to `null`.

A schema migration often goes hand in hand with some sort of data migration as you most likely have to touch existing data to make it fit into the new schema. Database migrations are important, especially in the context of agile software development where requirements change frequently. You do not want to invest months into planning your schema but instead change it incrementally together with your code.

The remainder of this post is structured as follows. The next section will discuss different strategies to perform database migrations. Afterwards we are going to look at Flyway, a database migration tool. Then we will introduce the Testcontainers project as a convenient way to test database migrations on real databases. We will conclude the post by summarizing the main findings.

# Migration Strategies

The simplest strategy is to log into the database, performing the migration *manually*. This might be fine for your personal pet project but is most likely not going to scale to a multi-developer or multi-environment setup.

The next step can be to write your migrations down in a *runbook*. This way other developers (including your future self) can understand which migrations were applied and what was executed.

If you want to avoid copy-pasting from the runbook you can create *migration scripts*, e.g. in the form of SQL files. When having an architecture where databases are not shared between services, it becomes natural to put those migration scripts alongside the source code of the service.

The ultimate form of automation can be achieved when executing the migrations scripts automatically, using *migration tools* such as [Flyway](https://flywaydb.org/) or [Liquibase](https://www.liquibase.org/). By using migration tools in combination with version control as well as automated and reproducible deployments you will be able to

- create new databases from scratch,
- make sure that all your databases are in the same, consistent state across environments, and
- migrate any database in a deterministic way to a new version.

Let's look at a concrete example using Flyway in the next section.

# Flyway Migrations

Flyway migrations can be written in SQL, where database specific syntax is supported, or in Java. Migration scripts are typically versioned and should be immutable. Once a migration is deployed, any new change needs to be done by introducing a new version. Migration scripts are organized alongside your source code, e.g. inside `src/main/resources`:

```
.
└── src
    └── main
        └── resources
            └── db_migrations
                ├── V1.0.0__Customer_table.sql
                ├── V1.0.1__Customer_id_index.sql
                └── V2.0.0__Product_table.sql
```

Each migration script contains the SQL statements that should be applied to your database when migrating to the new version. The creation of the customer table and then adding an index to the customer ID might look like this:

```sql
-- V1.0.0__Customer_table.sql
create table customers (
    id int,
    last_name varchar(255),
    first_name varchar(255)
);
```

```sql
-- V1.0.1__Customer_id_index.sql
create unique index customer_id
  on customers (id)

```

Flyway can be invoked either from the command line, through build tools such as Gradle or Maven, or using the Flyway Java API. The available commands are *migrate*, *clean*, *info*, *validate*, *undo*, *baseline*, and *repair*. The migrate command is the most important one as it issues a new migration to an existing database. We will not go into further detail about the other commands this point. Feel free to check out the [documentation](https://flywaydb.org/documentation/) for more information.

The following Kotlin code shows how to perform a migration of a PostgreSQL database.

```kotlin
val (host, port, dbName, username, password) = getConnectionDetails()
val jdbcUrl = "jdbc:postgresql://$host:$port/$dbName"

Flyway.configure()
    .dataSource(jdbcUrl, username, password)
    .load()
    .migrate()
```

# Testing Migrations With Testcontainers

Now that we have defined our migrations how can we test them as part of our automated tests? When I started developing web applications it was state of the art to use an in-memory database such as [H2](https://www.h2database.com/html/main.html) for local development and connect to your PostgreSQL installation in production.

In order to test our migrations we could start the in-memory DB, perform the migration, and then execute SQL statements to verify that the migration has been performed as expected. If we do it this way, however, we cannot use PostgreSQL specific syntax or functionality within our migrations. In many use cases this is a show stopper. What we would need is a fresh PostgreSQL database, automatically created for each test case. Is that possible?

[Testcontainers](https://www.testcontainers.org/) to the rescue! Testcontainers is a Java library that integrates with JUnit to provide throwaway instances of databases and other services in form of Docker containers. If you are using JUnit 5, you can simply use the Testcontainers extension. The following Kotlin code demonstrates how to test our migration on a real PostgreSQL database.

```kotlin
@Testcontainers
class DatabaseMigrationsTest {

  @Container
  val postgresContainer = PostgresContainer("postgres:10.6")
    .withDatabaseName("db")
    .withUsername("user")
    .withPassword("password")

  @Test
  fun testSomethingOnYourCustomerTable() {
    testAfterMigration(postgresContainer) { pgClient ->
      val one = pgClient.preparedQueryAwait("select 1 from customers")
        .first()
        .getInt(0)
      assertThat(one).isEqualTo(1)
    }
  }

}
```

The `testAfterMigration` function is a helper function that first applies the migration, creates a [reactive PostgreSQL client](https://github.com/vietj/reactive-pg-client/) and passes it to the test function. The code below shows the gist of it. To keep the code short I hid details of running the migrations and creating the database client in the `migrate` and `createPgClient` functions, respectively. The `connectionDetails` property of the container object are custom code to access the database connection details in a convenient way.

```kotlin
fun testAfterMigration(postgresContainer: PostgresContainer, testFunction: suspend (PgClient) -> Unit) {
  migrate(postgresContainer.connectionDetails)
  val pgClient = createPgClient(postgresContainer.connectionDetails)
  runBlocking {
      testFunction(pgClient)
  }
}
```

# Summary

In this post we have discussed the concept and importance of database migrations in the context of agile software development. By using migration tools in combination with version controlled migration scripts and automated deployments you can create new databases from scratch and migrate existing database instances in a deterministic way. Thanks to Testcontainers, developers can conveniently test their migrations as part of their automated tests, connecting to real databases during test execution.

How are you doing your database migrations? Have you ever used a tool like Flyway or Liquibase? Did you run into any issues or do you have success stories you would like to share? Let me know your thoughts in the comments!

---

Cover image by [Christophe Benoit](https://www.flickr.com/photos/christophebenoit/21828243446/)
