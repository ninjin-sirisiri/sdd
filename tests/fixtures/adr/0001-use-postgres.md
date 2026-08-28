# 0001. Use Postgres for the write model

We needed a durable write model. We chose Postgres over a document store because we need transactions across order lines.
