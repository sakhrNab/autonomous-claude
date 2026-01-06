---
name: api-design
description: "Design RESTful and GraphQL APIs following best practices."
allowed-tools: Read, Write, Edit
---

# API Design Skill

## REST Principles

### Resource Naming
- Use nouns: `/users`, `/orders`
- Use plurals: `/users` not `/user`
- Nested resources: `/users/{id}/orders`

### HTTP Methods
- GET: Read resource
- POST: Create resource
- PUT: Replace resource
- PATCH: Update resource
- DELETE: Remove resource

### Status Codes
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Server Error

## GraphQL Patterns

### Schema Design
```graphql
type User {
  id: ID!
  name: String!
  email: String!
  orders: [Order!]!
}

type Query {
  user(id: ID!): User
  users(limit: Int): [User!]!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
}
```

## Authentication

- JWT for stateless auth
- OAuth2 for third-party
- API keys for server-to-server

## Output

Always provide:
- Endpoint definitions
- Request/response schemas
- Example requests
- Error responses
