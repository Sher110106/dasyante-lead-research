# Research Brief: Automated B2B Lead-Generation Agent for Dasyante

## 1. Context: What is Dasyante?

Dasyante is building a **model-agnostic trust and memory infrastructure layer for AI applications**.

The core problems we want to solve are:

* AI agents produce hallucinated or unverifiable answers.
* AI systems lose or incorrectly resolve information across sessions.
* AI-generated facts are difficult to trace back to authoritative sources.
* Teams building AI agents/c copilots often create ad-hoc solutions using vector databases, prompts, wrappers, manual QA, and guardrails.
* The target customer is primarily an AI/ML engineering team building **customer-facing AI agents or copilots**, particularly where correctness, provenance, consistency, and persistent memory matter.

Our current target buyer hypotheses include:

* CTO
* Head/VP of AI
* Head of AI Engineering
* VP Engineering
* Head of Applied AI
* Director of AI/ML
* AI/ML Engineering Lead

We believe the strongest prospects are companies where several of the following signals are present:

### High-intent signals

1. Hiring AI Agent Engineers
2. Hiring LLM Evaluation / AI Evaluation engineers
3. Hiring AI Platform / LLM infrastructure engineers
4. Recently launched an AI agent
5. Recently launched a customer-facing AI copilot/assistant
6. Uses multiple LLM providers such as OpenAI, Anthropic, Gemini, etc.
7. Uses frameworks such as LangChain, LangGraph, LlamaIndex, CrewAI, etc.
8. Publicly discusses hallucination, evaluation, grounding, RAG, AI reliability, memory, provenance, or consistency
9. Has enterprise customers
10. Operates in a regulated/high-consequence industry
11. Has AI products involving multi-session workflows or persistent user context
12. Uses AI to make recommendations, generate reports, or take actions for customers

The goal is NOT simply to find "AI companies."

The goal is to identify companies that are **likely to have the specific Dasyante problem**.

---

# 2. What we want to build

We want an automated **Dasyante Lead Research Agent**.

Conceptually:

LinkedIn / Sales Navigator / other company discovery source
↓
Find candidate companies
↓
Company enrichment
↓
AI/product/technology research
↓
Detect high-intent signals
↓
Collect evidence for each signal
↓
Calculate Dasyante Fit Score (0–100)
↓
Discard low-quality prospects
↓
For high-scoring companies:
find relevant decision-makers
↓
Find verified business contact information
↓
Output qualified leads
↓
Potentially generate personalized outreach based on the evidence

---

# 3. Desired end-to-end workflow

We want to investigate the best tools/APIs/agents for each stage.

## Stage A — Company discovery

We need a way to discover candidate companies.

Potential sources:

* LinkedIn
* LinkedIn Sales Navigator
* Apollo
* Crunchbase
* Wellfound
* G2
* Product Hunt
* company databases
* job boards
* other B2B databases

We want to understand:

* Which platform is best for finding companies matching our ICP?
* Can it search by company size?
* Industry?
* Geography?
* AI/engineering headcount?
* Hiring activity?
* Job openings?
* Technologies?
* Recent growth?
* Funding?
* AI-related keywords?
* Can it be automated through an official API/integration?
* Does it allow programmatic access?
* What are the pricing/usage limitations?

IMPORTANT:

We do NOT want to build an unsafe or ToS-violating LinkedIn scraper that logs into a personal LinkedIn account and automatically scrapes LinkedIn.

Prefer:

* official APIs
* approved integrations
* supported browser extensions
* native automation capabilities
* compliant third-party data providers

If LinkedIn automation is not officially supported, explain the best compliant alternative.

---

# 4. Stage B — Company enrichment

Once we have:

Company Name
Company Website
LinkedIn URL (if available)

we want to enrich the company.

Potential tools:

* Clay
* Apollo
* Crunchbase
* Clearbit/Breeze
* People Data Labs
* BuiltWith
* 6sense
* ZoomInfo
* other enrichment APIs

We want to determine:

* company name
* website
* industry
* employee count
* location
* funding
* estimated revenue if available
* enterprise vs SMB focus
* technology stack
* AI/ML team size
* recent hiring
* recent funding
* recent product launches
* relevant news

Determine which tool is strongest for each of these.

---

# 5. Stage C — Detect Dasyante pain signals

This is the MOST IMPORTANT part.

We want an AI research agent to investigate a company and determine whether it exhibits our high-intent signals.

Potential sources to investigate:

* company website
* product pages
* documentation
* engineering blog
* company blog
* careers page
* job postings
* LinkedIn company posts
* public GitHub repositories
* press releases
* news
* interviews
* podcasts/transcripts
* technical articles
* public customer case studies

For each signal, we want:

Signal:
YES / NO / UNKNOWN

Evidence:
specific evidence supporting the conclusion

Source:
URL

Confidence:
0–100

Example:

Signal:
"Company has a customer-facing AI agent"

Result:
YES

Evidence:
"The company launched an AI agent that autonomously handles customer support workflows."

Source:
[URL]

Confidence:
94

We need to research which tools can perform this kind of automated web/company research reliably.

Candidates include:

* Clay AI research
* browser agents
* Perplexity-style research APIs
* Tavily
* Exa
* Firecrawl
* Serper
* Google/Bing search APIs
* custom LLM + web search
* other agentic research systems

Compare them.

---

# 6. Stage D — Dasyante Fit Score

We want a scoring system between 0 and 100.

Potential scoring:

Customer-facing AI agent: +15
Multi-session memory/context: +20
LLM evaluation/reliability activity: +20
Public hallucination/reliability discussion: +20
AI-agent hiring: +15
Multiple LLM providers: +10
Enterprise customers: +10
Regulated industry: +10
AI-generated recommendations/decisions: +10
Relevant AI frameworks: +5
Recent funding: +5
Rapid AI hiring: +5

These weights are provisional.

Research whether there are better ways to construct the scoring system.

Important:

The score should be based on **evidence**, not simply keyword matching.

We want to distinguish:

"Company mentions AI"

from:

"Company has a customer-facing multi-session AI agent and is actively hiring LLM evaluation engineers."

The second should score much higher.

Research whether an LLM-based scoring agent, deterministic rules, or a hybrid system would work best.

---

# 7. Stage E — Decision-maker identification

For companies above a threshold, e.g. 80/100, find relevant people.

Target titles:

* CTO
* VP Engineering
* Head of AI
* Head of AI Engineering
* Head of Applied AI
* VP AI
* Director of AI
* Director of Machine Learning
* AI Engineering Lead
* ML Engineering Lead
* Head of ML
* Head of Platform
* Head of AI Infrastructure

Research the best platform for finding these people.

Candidates:

* Apollo
* LinkedIn Sales Navigator
* Clay
* ZoomInfo
* Cognism
* People Data Labs
* Hunter
* others

We want:

Name
Title
Company
LinkedIn URL
Work email
Email confidence/verification
Relevant role
Reason this person is likely the right buyer

---

# 8. Stage F — Contact enrichment

Once the correct decision-maker is identified, determine the best system for finding:

* verified work email
* LinkedIn profile
* company
* role
* location
* other useful contact information

We care about:

* accuracy
* freshness
* email verification
* cost per contact
* API availability
* automation
* international coverage

Compare Apollo, Hunter, Dropcontact, Cognism, ZoomInfo, Clay and alternatives.

---

# 9. Stage G — Personalized outreach

Eventually, the system should be able to generate a highly personalized first message.

However, this is NOT the first priority.

The message should be generated from the evidence discovered during research.

Example:

Company:
XYZ

Evidence:

* launched customer-facing AI agent in March
* hiring two AI evaluation engineers
* uses multiple LLM providers
* enterprise customers

Generated reasoning:

"XYZ is likely dealing with reliability and consistency challenges as its customer-facing agent scales across models and sessions."

Then create a concise outreach message referencing the relevant public evidence.

We want to avoid generic:

"Hi, I saw your company uses AI..."

Instead:

"I noticed you're expanding your AI evaluation team while scaling your customer-facing agent..."

Research the best tools for this stage, but treat it as Phase 2 rather than the initial MVP.

---

# 10. Desired final output

For every qualified lead, we ultimately want something like:

Company:
XYZ AI

Website:
xyz.ai

Dasyante Score:
91/100

Why:

* Customer-facing AI agent
* Persistent user context
* Hiring LLM evaluation engineers
* Multiple LLM providers
* Enterprise customers

Evidence:

1. AI agent launch → URL
2. LLM evaluation job → URL
3. Multi-model architecture → URL
4. Enterprise customer → URL

Decision Maker:
Jane Doe

Title:
VP Engineering

LinkedIn:
URL

Business Email:
[jane@xyz.ai](mailto:jane@xyz.ai)

Email confidence:
95%

Recommended outreach angle:
"AI agent reliability + cross-session consistency"

---

# 11. What we want you to research

Do a comprehensive comparison of the available tools and architectures for building this system.

For EACH stage, determine:

1. Best tool
2. 2–3 alternatives
3. Official API availability
4. Automation capabilities
5. Whether it can integrate with Clay
6. Pricing
7. Approximate cost per 1,000 companies/contacts/research operations
8. Data quality
9. Coverage
10. Rate limits
11. Ease of implementation
12. Whether it requires a human in the loop
13. Terms-of-service / compliance considerations
14. Strengths
15. Weaknesses

The stages to evaluate are:

A. Company discovery
B. LinkedIn/Sales Navigator discovery
C. Company enrichment
D. Job/hiring signal detection
E. Technology-stack detection
F. Website/web research
G. AI-product detection
H. Hallucination/reliability/memory signal detection
I. Evidence collection
J. Lead scoring
K. Decision-maker identification
L. Email/contact enrichment
M. Email verification
N. Personalized outreach
O. Workflow orchestration

---

# 12. Specifically investigate these tools

At minimum investigate:

* LinkedIn Sales Navigator
* Apollo
* Clay
* ZoomInfo
* Cognism
* Hunter
* People Data Labs
* Crunchbase
* BuiltWith
* Clearbit/Breeze
* 6sense
* Instantly
* Smartlead
* Firecrawl
* Tavily
* Exa
* Serper
* Google/Bing search APIs
* relevant browser/agent automation tools
* relevant workflow automation platforms such as n8n, Make, Zapier, etc.

Also identify better alternatives if they exist.

---

# 13. Important architectural question

We specifically want you to answer:

### Is Clay actually the right central platform?

Compare these architectures:

Architecture A:

LinkedIn → Clay → Apollo → Outreach

Architecture B:

Sales Navigator → Apollo → Clay → Outreach

Architecture C:

Apollo → Clay → Apollo

Architecture D:

Search API → AI Research Agent → Database → Apollo → Outreach

Architecture E:

n8n/Make → discovery APIs → Clay → Apollo → CRM

Architecture F:

Custom agent/orchestrator → multiple APIs

Determine which architecture is best for:

* MVP
* low budget
* fastest deployment
* high-volume prospecting
* highest-quality leads
* long-term scalable product

---

# 14. MVP requirement

We do NOT need a huge enterprise system initially.

Design the simplest system that can take:

> 100 candidate companies

and produce:

> 10–30 highly qualified Dasyante prospects

with:

* Dasyante Fit Score
* evidence
* decision-maker
* verified business email
* reason for qualification

We want to minimize:

* unnecessary API costs
* unnecessary enrichment
* manual work
* false positives

Especially important:

**Do not spend expensive contact-enrichment credits on companies that fail the Dasyante qualification stage.**

The ideal sequence is:

Company discovery
→ cheap filtering
→ signal research
→ scoring
→ only then decision-maker/contact enrichment.

---

# 15. Final recommendation format

At the end, provide:

### Recommended MVP Stack

Example:

Discovery:
???

Research:
???

Enrichment:
???

Scoring:
???

Decision-maker:
???

Email:
???

Automation:
???

Database/CRM:
???

Outreach:
???

Then provide:

### Exact MVP Workflow

Step 1 → ...
Step 2 → ...
Step 3 → ...
...

### Estimated cost

For:

100 companies
1,000 companies
10,000 companies

### What should be automated vs human-reviewed

### What should NOT be automated

### Biggest technical risks

### Biggest data-quality risks

### LinkedIn/automation compliance risks

### Recommended first experiment

We are specifically trying to determine the **best practical, compliant, low-cost architecture for automatically discovering high-intent B2B prospects for Dasyante**, rather than merely assembling a generic sales-tech stack.

