## Principal Data Engineer (P5) – Take-Home Technical Assessment

**Focus areas:** Data architecture, required Python programming assignment, data modeling, orchestration, data quality, CI/CD, governance, cost, and security
**Recommended completion time:** 2–3 hours

---

### Overview

Thank you for taking part in the interview process.

This exercise is designed to evaluate practical judgment, technical depth, software engineering discipline, and communication skills for a Principal Data Engineer role. We are less interested in perfect syntax or building a fully productionized system, and more interested in how you design reliable data pipelines, structure code, manage trade-offs, and explain decisions in a way that could scale across teams.

Your solution should demonstrate modern data engineering practices: modular pipeline design, clear data contracts, automated quality checks, secure handling of sensitive data, cost-aware processing, and maintainable delivery through version control and CI/CD.

---

### Objective

Demonstrate your ability to:

- Design a scalable data pipeline from raw source data to curated analytical outputs.
- Apply sound data modeling and transformation principles.
- Implement a required Python-based data engineering utility or pipeline component to demonstrate programming ability.
- Include data quality checks, validation rules, and failure-handling strategy.
- Describe orchestration and CI/CD practices for safe, repeatable delivery.
- Address security, governance, lineage, observability, and cost optimization.
- Communicate assumptions, design decisions, and trade-offs clearly.

---

### Time Expectation

Please spend approximately **2–3 hours** on this exercise.

The assessment is intentionally scoped to evaluate approach, judgment, and engineering quality rather than exhaustive completeness. If you do not complete every item, document what you would do next and why.

---

### Submission Instructions

- Submit a Git repository or compressed folder containing all source files.
- Include a `README.md` with:
  - Setup steps
  - Assumptions
  - Design notes
  - Trade-offs considered
  - How to run or validate the solution
- Include representative sample data or generated mock data if needed.
- Do not include credentials, secrets, real patient data, customer data, or real company-specific information.
- If using synthetic data, clearly state that it is synthetic.

---

### Scenario

Your team supports internal analytics and data product use cases across multiple engineering and business functions. Source systems produce operational data in files, APIs, databases, and event streams. The organization wants a repeatable data pipeline pattern that can ingest raw data, validate and standardize it, publish curated datasets, and support downstream analytics, reporting, and machine learning use cases.

The organization also wants the solution to be production-minded: secure, observable, cost-efficient, maintainable, and suitable for controlled promotion between environments such as dev, test, and prod.

For this exercise, assume you are building the first version of a reusable pipeline pattern for a new data product.

---

## Required Deliverables

### A. Data Architecture and Design

Create a concise architecture proposal for a data pipeline that moves data from raw ingestion to curated consumption.

Your design should include:

- A logical architecture using layered data zones such as raw/bronze, cleaned/silver, and curated/gold, or an equivalent pattern.
- The intended consumers of each layer.
- How batch, incremental, or streaming ingestion would be handled.
- How schema evolution, late-arriving data, duplicate records, and reprocessing would be managed.
- How the design supports auditability, traceability, and replayability.
- How sensitive data would be protected across storage, processing, and consumption.
- How cost would be controlled through partitioning, clustering, file sizing, lifecycle policies, or compute optimization.

**Architecture expectations:**

- Clear separation of concerns between ingestion, transformation, validation, and consumption.
- Reusable design rather than one-off scripts.
- Explicit assumptions about data volume, latency, freshness, and reliability requirements.
- Practical discussion of trade-offs, including managed vs. self-managed services and batch vs. streaming patterns.
- Awareness of modern lakehouse or warehouse patterns using tools such as Apache Iceberg, cloud object storage, Spark, Trino, Snowflake, or equivalent platforms.

---

### B. Required Python Programming Assignment

Implement a small but representative **Python-based data engineering pipeline component**. This section is required and is intended to evaluate hands-on programming skills, code organization, maintainability, and practical data engineering judgment.

The implementation must use Python as the primary programming language. You may use pandas, PySpark, standard-library modules, or other appropriate Python libraries. SQL, dbt, or orchestration tools may be included as supporting artifacts, but they do not replace the required Python submission.

Minimum expectations:

- Provide a runnable Python script, package, or command-line utility.
- Read input data from one or more structured files such as CSV, JSON, or Parquet.
- Validate required fields and expected data types.
- Clean, normalize, and standardize the data.
- Deduplicate records using a clear and documented business rule.
- Produce at least one curated output dataset suitable for analytical consumption.
- Include meaningful logging or execution output.
- Include clear error handling for invalid input, missing files, bad schemas, or malformed records.
- Structure the code so it is maintainable and easy to extend.
- Include a short explanation of design choices, assumptions, and trade-offs in the README.

Python programming expectations:

- Clear separation of responsibilities, such as input parsing, validation, transformation, and output writing.
- Readable, idiomatic Python with meaningful names and simple control flow.
- Avoidance of hard-coded paths, magic constants, and unnecessary global state.
- Appropriate use of functions, classes, or modules where they improve clarity.
- Type hints where useful.
- Unit-testable design, even if only a small test suite is included.
- Practical handling of edge cases, malformed input, duplicates, null values, and timestamp parsing.
- Preference for simple, maintainable code over overly clever or over-engineered solutions.

**Example input fields** may include:

```json
{
  "event_id": "evt-001",
  "source_system": "crm",
  "customer_id": "cust-123",
  "event_type": "account_updated",
  "event_timestamp": "2026-01-15T10:30:00Z",
  "amount": 125.50,
  "currency": "USD",
  "ingestion_timestamp": "2026-01-15T10:35:00Z"
}
```

You may adjust the dataset domain if you prefer, but keep the problem simple enough to complete within the recommended time.

---

### C. Data Quality, Contracts, and Testing

Add or describe data quality controls that would prevent poor-quality data from silently reaching consumers.

Minimum expectations:

- Define required fields and validation rules.
- Include checks for uniqueness, nullability, accepted values, referential integrity, or timestamp validity where applicable.
- Show how invalid records would be handled, such as quarantine, reject, warning, or fail-fast behavior.
- Include at least one unit test for the Python implementation, plus any additional data test or pseudo-test you find useful.
- Describe how quality checks would run in CI/CD and during scheduled pipeline execution.

You may use tools or patterns such as:

- pytest
- dbt tests
- custom validation code
- data contracts or schema registry patterns

---

### D. Orchestration and Operational Design

Provide a small orchestration example or pseudo-workflow showing how the pipeline would run in production.

You may use:

- AWS Step Functions
- Apache Airflow
- GitLab scheduled pipelines
- another appropriate orchestrator

Minimum expectations:

- Show pipeline stages and dependencies.
- Distinguish ingestion, validation, transformation, publication, and monitoring steps.
- Explain retry behavior, idempotency, and failure handling.
- Explain how backfills or reprocessing would be performed safely.
- Describe how freshness and SLA/SLO monitoring would work.
- Include how lineage or metadata would be captured where practical.

---

### E. CI/CD and Delivery Practices

Create a small `.gitlab-ci.yml` or pseudo-pipeline definition for validating and promoting the data pipeline.

Minimum expectations:

- Include stages for:
  - Format/lint
  - Python linting and unit tests
  - Data quality or contract checks
  - Build/package
  - Deploy or promote
- Show different behavior for merge requests versus the default branch.
- Include at least one controlled gate before production deployment.
- Explain what failures should block promotion.
- Explain how environment-specific configuration would be managed.
- Explain how secrets and credentials would be protected.

**This does not need to be fully executable.** A well-structured pipeline skeleton with clear reasoning is sufficient.

---

### F. README and Design Explanation

Your `README.md` should explain:

- How to run the required Python script or package locally.
- Key assumptions and constraints.
- Repository structure.
- Data flow from source to curated output.
- Data quality checks and expected behavior on failure.
- Security and privacy considerations.
- Cost optimization considerations.
- Observability, monitoring, and lineage strategy.
- What you would add next for production readiness.

---

## What We Are Looking For

### Production-Minded Data Engineering

- A practical design rather than a minimal toy example.
- Clear thinking about operational reliability, failure modes, and supportability.
- Patterns that could be reused by other teams or data products.
- Reasonable assumptions and clearly documented trade-offs.

### Software Engineering Excellence

- Clean, maintainable, modular code.
- Clear abstraction boundaries and minimal duplication.
- Consistent naming, structure, and style.
- Meaningful tests and validation.
- Idempotent processing where appropriate.
- Simplicity over unnecessary complexity.
- Documentation that enables future engineers to understand and extend the solution.

### Data Modeling and Data Product Thinking

- Clear distinction between raw, cleaned, and curated data.
- Thoughtful modeling of analytical outputs.
- Awareness of dimensional modeling, wide tables, facts/dimensions, aggregates, or domain-oriented data products.
- Consideration of downstream consumers and access patterns.
- Explicit handling of schema changes and backward compatibility.

### Data Quality, Observability, and Lineage

- Quality checks embedded into the delivery process.
- Clear handling of invalid or late-arriving data.
- Metrics for freshness, volume, error rate, and completeness.
- Ability to trace data from output back to source.
- Operational visibility into pipeline success, failure, and performance.

### Security, Privacy, and Governance

- Secure-by-default mindset.
- Least-privilege access design.
- Protection of secrets and credentials.
- Encryption in transit and at rest where applicable.
- Separation of environments.
- Consideration of sensitive data classification, masking, tokenization, or anonymization where applicable.
- Auditability and traceability of data access and pipeline changes.

### Cost and Performance Optimization

- Efficient use of compute and storage.
- Avoidance of unnecessary full refreshes where incremental processing is appropriate.
- Partitioning, clustering, compaction, pruning, or caching considerations.
- Awareness of storage lifecycle and retention costs.
- Practical balance between freshness, reliability, performance, and cost.

### Communication

- Clear written explanations.
- Explicit assumptions.
- Practical trade-off analysis.
- Ability to explain design decisions to both technical and non-technical stakeholders.

---

## Evaluation Criteria

Candidates will primarily be assessed across the following areas:

| Area | Weight |
| --- | ---: |
| Data Architecture and Pipeline Design | 20% |
| Python Programming, Transformation Implementation, and Code Quality | 25% |
| Data Quality, Testing, and Reliability | 20% |
| Orchestration, CI/CD, and Operational Readiness | 15% |
| Security, Governance, and Privacy | 10% |
| Cost and Performance Optimization | 5% |
| Documentation and Communication | 5% |

The strongest submissions demonstrate balanced decision-making across reliability, maintainability, data trust, security, scalability, cost, and strong hands-on programming discipline. We do not expect a fully enterprise-grade platform in 2–3 hours, but we do expect evidence of how you would think, code, and operate at Principal Engineer level.

---

## Optional Stretch Items (Not Required)

- Add dbt models with tests and generated documentation.
- Add Great Expectations or equivalent data quality checks.
- Use Apache Iceberg-style table design.
- Demonstrate incremental processing or change data capture handling.
- Add lineage metadata using OpenLineage, DataHub, or equivalent patterns.
- Add observability metrics for freshness, volume, processing time, and error rates.
- Add cost estimation or compute optimization notes.
- Add a simple data contract or schema registry example.
- Add containerization or reproducible local development setup.
- Add richer Python unit tests, static typing checks, or packaging structure.
- Add policy checks, access control examples, or sensitive-data masking.

---

## Next Step

During the next interview round, you will be asked to walk through your solution and discuss:

- Architecture choices and trade-offs
- Data modeling decisions
- Python implementation, transformation logic, and code structure
- Data quality strategy
- Failure handling, retries, and reprocessing
- Orchestration and CI/CD approach
- Security, governance, privacy, and access controls
- Cost and performance optimization
- How the solution would evolve to support broader organizational scale

The discussion is intended to evaluate both technical depth and Principal-level engineering judgment.
