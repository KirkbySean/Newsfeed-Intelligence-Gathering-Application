# Newsfeed Intelligence Gathering Application

A local, multi-agent intelligence gathering application that collects news articles from RSS feeds, analyzes their relevance to a defined objective, researches related reporting, produces structured assessments, and generates periodic intelligence reports.

The application uses locally hosted large language models through Ollama and stores article data, agent outputs, and reports in a SQLite database.

## Overview

The application is designed as a sequential multi-agent pipeline:

```text
RSS News Feed
      |
      v
Article Collection
      |
      v
Initial Analysis
      |
      v
Contextual Research
      |
      v
Assessment
      |
      v
Report Generation
```

Each stage performs a different task and passes information to subsequent stages through a shared SQLite database.

The current implementation uses a European security/NATO-related analytical objective as a demonstration use case. The agent prompts and data sources can be modified to support other news-monitoring and research objectives.

## Pipeline

### 1. Article Collection — `collect.py`

The collection stage reads articles from an RSS news feed.

For each new RSS entry, the application:

* Checks whether the article has already been collected.
* Downloads the article webpage.
* Extracts the article text using BeautifulSoup.
* Stores the article and associated metadata in SQLite.
* Skips duplicate articles and pages from which article text cannot be extracted.

The current implementation uses the BBC News RSS feed, but additional RSS feeds can be added.

### 2. Initial Analysis — `analyze.py`

The first LLM agent reviews newly collected articles and determines their relevance to the application's analytical objective.

The agent produces structured output including information such as:

* Relevance
* Article category
* Analysis summary
* Reasoning for the relevance determination

Articles that are considered relevant can then progress to the research stage.

### 3. Contextual Research — `research.py`

The research agent attempts to place new reporting into the context of previously collected information.

It can search the local article database for related reporting and use those previous articles to identify relevant historical context and connections between developments.

This allows the system to build upon information collected during previous pipeline runs rather than analyzing every article in isolation.

### 4. Assessment — `assessment.py`

The assessment stage combines the current article, its initial analysis, and contextual research to produce a more complete structured assessment.

The resulting assessment can contain:

* An assessment summary
* Key developments
* Uncertainties
* Confidence information
* Supporting article relationships

These assessments provide the primary input to the final reporting stage.

### 5. Report Generation — `generate_report.py`

The reporting agent retrieves assessments from the configured reporting period and combines them into a higher-level report.

Generated reports contain:

* Executive summary
* Key developments
* Detailed assessment
* Uncertainties
* Source article references

Reports are stored in the SQLite database and exported as human-readable text files in the `reports/` directory. There is a sample report in this folder as an example of what a report may look like.

## Pipeline Orchestration

The complete application can be run using:

```bash
python run_pipeline.py
```

`run_pipeline.py` executes each stage sequentially:

```text
collect.py
    ↓
analyze.py
    ↓
research.py
    ↓
assessment.py
    ↓
generate_report.py
```

If one stage fails, the pipeline stops rather than continuing with potentially incomplete data.

Individual agents can also be executed independently during development or testing.

## Requirements

### Python

Python 3.10 or newer is recommended.

The primary Python dependencies are:

* Ollama Python client
* Pydantic
* Feedparser
* Requests
* BeautifulSoup4

Install the dependencies with:

```bash
pip install -r requirements.txt
```

### Ollama

The application uses Ollama to run the LLM locally.

Install Ollama for your operating system before running the pipeline.

The default model is:

```text
qwen3:14b
```

After installing Ollama, download the model with:

```bash
ollama pull qwen3:14b
```

You can verify that the model is installed with:

```bash
ollama list
```

Because Qwen3 14B is a relatively large local model, sufficient system memory and/or GPU memory is recommended.

## Configuration

Application-wide configuration is located in:

```text
config.py
```

The current configuration contains:

```python
OLLAMA_MODEL = "qwen3:14b"
DATABASE_PATH = "articles.db"
```

To use another Ollama-compatible model, change `OLLAMA_MODEL`.

For example:

```python
OLLAMA_MODEL = "another-model"
```

The same model configuration is then available to the different agents.

## Installation

Clone the repository:

```bash
git clone <repository-url>
```

Move into the project directory:

```bash
cd Newsfeed-Intelligence-Gathering-Application
```

Optional but recommended: create a Python virtual environment.

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

Install Ollama separately and download the configured model:

```bash
ollama pull qwen3:14b
```

The application can then be started with:

```bash
python run_pipeline.py
```

## Project Structure

```text
Newsfeed-Intelligence-Gathering-Application/
│
├── collect.py              # RSS collection and article extraction
├── analyze.py              # Initial article analysis agent
├── research.py             # Contextual research agent
├── assessment.py           # Assessment agent
├── generate_report.py      # Final report generation
│
├── run_pipeline.py         # Pipeline orchestrator
├── config.py               # Application configuration
├── requirements.txt        # Python dependencies
│
├── reports/                # Generated reports/sample reports
└── README.md
```

## Data Storage

SQLite is used as the application's persistent storage layer.

The database maintains the state of articles as they progress through the pipeline, allowing agents to identify which articles have already been analyzed, researched, or assessed.

This also allows information collected during previous runs to provide context for newly collected reporting.

The generated database is not included in the repository and is created locally when the application is run.

## Design Goals

This project was developed to explore several concepts related to local LLM applications:

* Multi-agent LLM workflows
* Structured LLM outputs
* Tool use by LLM agents
* Retrieval of previously collected information
* Persistent agent state using SQLite
* Automated RSS and web-content ingestion
* Local LLM inference
* Multi-stage report generation
* Pipeline orchestration and failure handling

A central design goal is to separate collection, analysis, research, assessment, and reporting into independent stages while maintaining continuity through a shared persistent data store.

## Current Limitations

This project is a proof-of-concept implementation rather than a production intelligence platform.

Some current limitations include:

* Article extraction depends on the HTML structure of the source website.
* The default configuration currently uses a single RSS news source.
* LLM output quality depends on the selected model and available context.
* The pipeline currently runs on demand rather than continuously.
* Article and agent processing is performed sequentially.
* The current analytical objective is defined through agent prompts rather than a user-facing configuration interface.

These areas provide opportunities for future development, including additional data sources, improved article extraction, scheduled collection, parallel agent execution, retrieval improvements, and configurable analytical objectives.

## Using Ollama and Qwen3 14B
For more information on how to setup Ollama and Qwen please refer to these links:
* https://ollama.com/download
* https://ollama.com/library/qwen3%3A14b

## Disclaimer

LLM-generated assessments may contain errors or misinterpret source material. Generated reports should therefore be treated as analytical aids rather than independently verified factual reporting or professional intelligence assessments.
