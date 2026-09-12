# Framework Architecture

This API automation framework separates test intent, API interaction, shared test setup, reporting, and continuous integration. The separation keeps endpoint changes localized to the API object layer while test modules stay focused on business behavior and assertions.

```mermaid
flowchart TB
    subgraph Execution[Execution Entry Points]
        Local[Local Developer\npython -m pytest]
        CI[GitHub Actions\nAPI Tests workflow]
    end

    subgraph TestLayer[Test Layer: tests/]
        AuthTests[test_auth.py\nLogin and authorization]
        OrderTests[test_orders.py\nCreation, lifecycle, cancellation]
        ExportTests[test_exports.py\nJob status and CSV download]
        Markers[pytest markers\nauth, orders, exports\nsmoke, negative, lifecycle, slow]
    end

    subgraph Support[Framework Support]
        Fixtures[conftest.py\nBase URL, health check, auth fixture\nUnique payload and correlation ID fixtures]
        Polling[framework/polling.py\nDeadline-based status polling]
        ApiClient[framework/api_client.py\nApiClient]
        AuthApi[AuthApi\n/auth/login]
        OrdersApi[OrdersApi\n/orders]
        ExportsApi[ExportsApi\n/exports]
    end

    subgraph Service[Service Under Test]
        Mock[server.js\nExpress mock API\nhttp://localhost:3000/v1]
        OrderState[Order state engine\nPENDING to PROCESSING to COMPLETED]
        ExportState[Export state engine\nPROCESSING to COMPLETED]
    end

    subgraph Results[Results and Evidence]
        Html[reports/api-test-report.html\nSelf-contained HTML report]
        Junit[test-results/junit.xml\nJUnit XML]
        Artifact[GitHub Actions artifact\napi-test-results]
    end

    Local --> TestLayer
    CI --> TestLayer
    CI --> Mock
    Markers --> AuthTests
    Markers --> OrderTests
    Markers --> ExportTests
    Fixtures --> ApiClient
    AuthTests --> Fixtures
    OrderTests --> Fixtures
    ExportTests --> Fixtures
    OrderTests --> Polling
    ExportTests --> Polling
    ApiClient --> AuthApi
    ApiClient --> OrdersApi
    ApiClient --> ExportsApi
    AuthApi --> Mock
    OrdersApi --> Mock
    ExportsApi --> Mock
    Mock --> OrderState
    Mock --> ExportState
    TestLayer --> Html
    TestLayer --> Junit
    Html --> Artifact
    Junit --> Artifact

    classDef entry fill:#e8f2ff,stroke:#2563eb,color:#172033,stroke-width:2px;
    classDef tests fill:#e8f8f1,stroke:#087f5b,color:#172033,stroke-width:2px;
    classDef framework fill:#fff4df,stroke:#ad6a00,color:#172033,stroke-width:2px;
    classDef service fill:#fcecee,stroke:#c83b4d,color:#172033,stroke-width:2px;
    classDef results fill:#edf6f6,stroke:#007d78,color:#172033,stroke-width:2px;

    class Local,CI entry;
    class AuthTests,OrderTests,ExportTests,Markers tests;
    class Fixtures,Polling,ApiClient,AuthApi,OrdersApi,ExportsApi framework;
    class Mock,OrderState,ExportState service;
    class Html,Junit,Artifact results;
```

## Responsibilities

| Layer | Components | Responsibility |
| --- | --- | --- |
| Test layer | `tests/test_*.py` | Expresses business workflows, expected HTTP outcomes, and response assertions. |
| API object layer | `framework/api_client.py` | Centralizes endpoint paths, request methods, headers, session reuse, and five-second request timeouts. |
| Test setup | `conftest.py` | Supplies the configurable base URL, startup health check, authenticated headers, and isolated request data. |
| Async support | `framework/polling.py` | Polls status endpoints with a deadline and includes the final response in timeout failures. |
| Test selection | `pytest.ini` and decorators | Provides endpoint and scenario markers for fast, focused execution. |
| Reporting | `pytest-html`, JUnit XML, `assets/report_style.css` | Produces a portable visual report and CI-compatible machine-readable test results. |
| CI | `.github/workflows/api-tests.yml` | Installs dependencies, starts the mock API, waits for readiness, executes tests, and uploads artifacts. |

## Request Flow

1. pytest loads `conftest.py`, reads `BASE_URL`, and checks that the login endpoint is reachable.
2. The session fixture authenticates once and provides the Bearer token for protected-route tests.
3. A test invokes an endpoint object such as `api_client.orders.create(...)`; it never constructs a URL directly.
4. `ApiClient` executes the request through a shared `requests.Session` with the standard timeout.
5. Stateful tests use `wait_for_status(...)` to poll only until the required status is observed or a meaningful timeout is raised.
6. pytest writes the styled HTML report and JUnit XML after the run; GitHub Actions uploads both as `api-test-results`.
