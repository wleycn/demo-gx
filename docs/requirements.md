The following is a detailed requirements summary for the **Principal Data Engineer (P5) Take-Home Technical Assessment** document. This task is designed to evaluate the candidate's practical judgment and technical depth in data architecture, Python programming, data quality, orchestration, CI/CD, governance, and cost/security.

### 0. Scenario Background

- You are building the first version of a **"reusable pipeline pattern"** for a **new data product**.
- Future source systems will include: **files, APIs, databases, event streams**.
- The pipeline must support **dev → test → prod** controlled promotion.
- **Design positioning**: a patterned, reusable reference implementation, not a one-off script. All architectural decisions must reflect this positioning.

### 🎯 Core Goals and Constraints

* **Role:** Principal Data Engineer (P5). The focus is on the ability to design reliable pipelines, code structure, trade-off analysis, and cross-team communication and scaling — not on perfect syntax or a fully productionized system.
* **Time budget:** Recommended **2-3 hours**. If not all items are completed, record follow-up plans and reasons.
* **Core principles:** Production-minded, modular design, explicit data contracts, automated quality checks, secure sensitive-data handling, cost awareness, and maintainable delivery.


---

### 📦 Submission Specifications

1. **Format:** Git repository or compressed archive.
2. **README.md (must include):**
   * Local run/validation steps.
   * Assumptions and design notes.
   * Trade-off analysis.
   * Repository structure and data flow description.
   * Security, privacy, cost, and observability strategies.
   * Production readiness follow-up improvement plan.
3. **Data requirements:** Use representative sample data or generated mock data; **strictly prohibited** from including credentials, keys, or real customer/patient data; if synthetic data is used, this must be explicitly stated.

---

### ✅ Six Required Delivery Modules

#### A. Data Architecture and Design (Weight 20%)

* **Layered design:** Adopt Raw/Bronze → Cleaned/Silver → Curated/Gold or an equivalent pattern, clearly identifying consumers for each layer.
* **Dimensional modeling awareness:** facts / dimensions partitioning, wide tables, aggregations, domain data products.
* **Ingestion strategy:** Describe batch, incremental, or streaming ingestion approaches.
* **Exception handling:** Define schema evolution, late-arriving data, duplicate records, and reprocessing mechanisms.
* **Auditability:** Support lineage, tracing, and replay.
* **Security and cost:** Describe sensitive-data protection measures; control cost through partitioning, clustering, file-size optimization, lifecycle policies, or compute optimization.
* **Design requirements:** Separation of concerns (ingestion/transformation/validation/consumption), reusable design, explicit data volume/latency/freshness assumptions, managed vs. self-managed service trade-off discussion, modern Lakehouse/Warehouse pattern awareness.

#### B. Python Programming Assignment (Weight 25% - **Core Required**)

* **Language requirement:** **Must use Python** as the primary language (pandas, PySpark, etc. may be used). SQL/dbt is auxiliary only and cannot replace Python.
* **Feature implementation:**
  * Read structured files (CSV/JSON/Parquet).
  * Validate required fields and data types.
  * Clean and standardize data.
  * Deduplicate based on explicit business rules.
  * Output at least one analysis-oriented Curated dataset.
  * Include meaningful logging and execution output.
  * Comprehensive error handling (invalid input, missing files, schema errors, malformed records).
  * **Code quality:** Separation of responsibilities, readability, avoid hardcoding/magic numbers, appropriate use of type hints, unit-test friendly, edge-case handling, simplicity over over-engineering.
  * Must provide a **runnable** Python script, package, or CLI tool. "A single local command that runs end-to-end" is a hard delivery standard, not a soft description in a feature list.
  * Example input data structure
  The default data template (JSON) provided by the examiner:

  ```json
  {
    "event_id": "string",
    "source_system": "string",
    "customer_id": "string",
    "event_type": "string",
    "event_timestamp": "timestamp",
    "amount": "number",
    "currency": "string",
    "ingestion_timestamp": "timestamp"
  }
  ```

#### C. Data Quality, Contracts, and Testing (Weight 20%)

* **Validation rules:** Define required fields, uniqueness, null checks, enum values, referential integrity, timestamp validity, etc.
* **Exception handling:** Define a processing strategy for invalid records (quarantine, reject, alert, or fail fast).
* **Testing requirements:** Include at least one Python unit test + additional data tests/pseudo-tests.
* **Integration description:** Describe how quality checks run in CI/CD and scheduled jobs.
* Optional tool list: `pytest`, `dbt tests`,
* Custom validation code
* Data contracts / schema registry patterns

#### D. Orchestration and Operations Design (Weight 15%)

* **Form:** Provide an orchestration example or pseudo-workflow (Airflow, Step Functions, GitLab CI, etc.).
* **Content requirements:**
  * Show stage dependencies (ingestion → validation → transformation → publish → monitoring).
  * Describe retry mechanisms, idempotency, and failure handling.
  * Explain safe backfill / reprocessing flows.
  * Describe freshness and SLA/SLO monitoring.
  * Include lineage / metadata collection plan.

#### E. CI/CD and Delivery Practices (Weight 15%)

* **Form:** `.gitlab-ci.yml` or pseudo-pipeline definition (need not be fully executable; skeleton + rationale suffices).
* **Stage requirements:** Format/Lint → Python Lint & Unit Test → Data quality/contract check → Build/Package → Deploy/Promote.
* **Key elements:**
  * Distinguish MR vs. default-branch behavior.
  * Set at least one controlled gate before production deployment.
  * Explicitly define failure conditions that block promotion.
  * Environment configuration management and secret protection.

#### F. README and Design Narrative (Weight 5%)

* Beyond basic run instructions, focus on: data flow, quality-check failure behavior, security/privacy considerations, cost optimization, observability and lineage strategy, and the future productionization path.

---

### ⚖️ Evaluation Dimension Weight Table


| Evaluation Area                          | Weight | Core Focus Points                               |
| :--------------------------------------- | :----- | :---------------------------------------------- |
| Python programming, transformation, and code quality | 25%    | Modularity, readability, testing, idempotency, simplicity |
| Data architecture and pipeline design    | 20%    | Clear layering, reusability, trade-off analysis, modern tech-stack awareness |
| Data quality, testing, and reliability   | 20%    | Embedded checks, exception handling, metric monitoring, lineage capability |
| Orchestration, CI/CD, and ops readiness  | 15%    | Dependency management, retry/idempotency, safe backfill, environment isolation |
| Security, governance, and privacy        | 10%    | Least privilege, encryption, masking, audit trail |
| Cost and performance optimization        | 5%     | Incremental processing, partitioning/clustering, storage lifecycle, cost-performance balance |
| Documentation and communication          | 5%     | Explicit assumptions, clear trade-offs, expression for both technical and non-technical audiences |

---

### 💡 Optional Stretch Items

*Not required, but can enhance competitiveness:*

* dbt models + tests + documentation generation
* Great Expectations or similar data quality frameworks
* Apache Iceberg table design / CDC incremental processing
* OpenLineage/DataHub lineage integration
* Observability metrics for freshness/volume/duration/error rate
* Cost estimation or compute optimization notes
* Data contracts / schema registry examples
* Containerization / reproducible local development environment
* Richer unit tests / static type checking / packaging structure
* Policy checks / access control / sensitive-data masking examples

### ⏭️ Follow-up Interview Preparation Tips

The next interview round will revolve around your submission. Be prepared to discuss in depth: architectural trade-offs, data modeling decisions, Python code structure, quality strategy, failure recovery, CI/CD approach, security governance, cost optimization, and how the solution scales to support organization-level growth. This is both a test of technical depth and an opportunity to demonstrate Principal-level engineering judgment.
