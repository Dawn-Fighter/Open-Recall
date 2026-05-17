

**HACKATHON**

**PROBLEM STATEMENTS**

Building AI Agents with cascadeflow and Hindsight

In this hackathon, you will build AI-powered applications using Hindsight, a memory system developed by Vectorize that allows AI agents to remember, recall, and improve over time.

You will also be using cascadeflow, an in-process runtime intelligence layer that optimizes cost, latency, and model routing—so your agent runs smarter without burning through API credits.

*Instead of building AI that forgets conversations and wastes money on every call, your project should demonstrate persistent memory, intelligent runtime control, or both.*

# **Why Are We Sponsoring This Hackathon?**

We believe young people are the future of this industry. The ideas, energy, and fresh perspective that come from builders early in their careers are exactly what push technology forward, and we want to invest in that.

We also know it is harder than ever for college grads to break into high-paying tech jobs. The bar keeps rising, job postings ask for years of experience on technologies that barely existed last year, and it can feel like the door is closing. We want to help pry it back open. A strong hackathon project is one of the most credible ways to prove you can build, and we want to give you a real platform to do that.

Most of all, we want you to showcase your creativity. Hindsight is a powerful memory layer and cascadeflow is a powerful runtime intelligence layer, and we are genuinely excited to see how you use them to bring your ideas to life. Build something that is unmistakably yours, and let this be the project you point to when someone asks what you can do.

# **Why This Hackathon Matters for Your Career**

The AI agent space is exploding, and companies are hiring people who can build, not just talk about it. This hackathon is your chance to walk away with a working project that demonstrates you can ship an AI agent that solves a real problem.

Here is what is at stake for you personally:

**Build Your Portfolio, Not Just a Weekend Toy**

The best hackathon projects don’t just win prizes. They become the thing you link on your LinkedIn profile, your GitHub pinned repo, and the story you tell in interviews for the next two years. And it wouldn’t be the first time a startup evolves out of a hackathon. Pick a problem that a real business would actually pay to solve, and build toward that.

**Learn by Doing What the Industry Needs Right Now**

Stateless chatbots are yesterday’s news. The frontier is agents with memory: agents that learn from past interactions, adapt to user behavior, and get better over time. And the reality of production AI is cost control: knowing which model to use, when to escalate, and how to enforce budgets. Hindsight and cascadeflow give you hands-on experience with both. That is a skill set that is immediately valuable.

**Ship Something You Would Actually Use**

The projects that stand out (to judges, to recruiters, to future collaborators) are the ones where the builder clearly cared about the problem. Don’t chase what sounds impressive. Build something that solves a pain point you have actually experienced.

# **Required Technology**

All teams must build their projects using at least one of the following:

| Hindsight Agent memory – retain, recall, reflect. Your agent remembers what it learned across sessions. | cascadeflow Runtime intelligence – makes your agent production-ready: cost control, budget enforcement, model routing, and a full audit trail of every decision your agent made.  |
| :---- | :---- |

Projects using both technologies together are encouraged but not required.

**Hindsight Official Links**

* Hindsight Documentation: https://hindsight.vectorize.io/

* GitHub: https://github.com/vectorize-io/hindsight

* Hindsight Cloud: https://ui.hindsight.vectorize.io

**cascadeflow Official Links**

* cascadeflow Documentation: https://docs.cascadeflow.ai/

* GitHub: https://github.com/lemony-ai/cascadeflow

* Quick Start: [https://docs.cascadeflow.ai/get-started/installation](https://docs.cascadeflow.ai/get-started/installation)

## **Resources**

You can use **Hindsight Cloud** to quickly get a Hindsight instance, or the **open source version**. Use promo code **MEMHACK515** to get $50 in free credits on Hindsight Cloud. *You add this AFTER you register in the billing section.*

Join the Hindsight Community Slack to ask any questions about how to use Hindsight.

cascadeflow is open source and free to use. Install via **pip install cascadeflow** (Python) or **npm install @cascadeflow/core** (TypeScript). No API key required for the library itself.

Questions and integration bugs: https://github.com/lemony-ai/cascadeflow/issues — **post your question there, it helps other builders too.**

Strongly suggested:

* Follow Vectorize on LinkedIn: [https://www.linkedin.com/company/vectorizeio/](https://www.linkedin.com/company/vectorizeio/) 

* Follow Vectorize on X: https://x.com/Vectorizeio

* Follow cascadeflow on Linkedin: [https://www.linkedin.com/company/cascadeflow](https://www.linkedin.com/company/cascadeflow) 

We recognize high quality projects and tag your work which can help you raise your visibility with potential employers.

# **LLM Access**

You can use any LLM you want, but **Groq** is super fast and has a generous free tier: https://groq.com/

Recommended models on Groq are **openai/gpt-oss-120b** and **qwen/qwen3-32b**, but make sure to have your agent ready to handle function calling errors.

| cascadeflow \+ Free Models cascadeflow supports Groq natively: same install, zero extra config. It also works with OpenRouter (100+ models, many free), Ollama for fully local runs, and HuggingFace. cascadeflow's model routing runs most queries on a free or cheap model and only escalates to a paid API when the quality gate requires it. Every escalation is logged and intentional, not accidental, and your free tier goes further as a result. |
| :---- |

## **Coding Agents**

You can use any coding agent you want (or code by hand), but here are some free options:

* https://openai.com/codex/

* https://jules.google.com/

* https://opencode.ai/ (can use with Ollama for local models or with most LLM providers)

You can also use https://claude.com/product/claude-code but it requires a paid subscription.

The easiest way to setup Hindsight in your project is with the hindsight-skills repository: [https://github.com/vectorize-io/hindsight-skills](https://github.com/vectorize-io/hindsight-skills)

If you’re using Claude Code just run this from your terminal (check the repo for Codex, OpenCode and other setup commands):

| git clone \--depth 1 https://github.com/vectorize-io/hindsight-skills.git \~/hindsight-skills cd \~/hindsight-skills && ./setup |
| :---- |

Once installed, use the slash function /hindsight-architect in your coding agent to set up Hindsight. 

There's also a skill for cascadeflow. It's a single file in the main repo — to add it to Claude Code, run:

| mkdir \-p \~/.claude/skills/cascadeflow curl \-sL https://github.com/lemony-ai/cascadeflow/raw/refs/heads/main/skills/cascadeflow/SKILL.md \-o \~/.claude/skills/cascadeflow/SKILL.md |
| :---- |

Then start a new Claude Code session and ask it to set up cascadeflow — the skill loads automatically.

## **Framework and Provider Integrations**

Both Hindsight and cascadeflow work natively with the most popular agent frameworks. Pick the one you already know — that is where your authentic voice is, and that is what will make your article genuinely interesting to other engineers.

 

**Agent Frameworks**

The table below shows which frameworks each technology integrates with. Rows with both ✅ are natural combined project stories.

 

| Framework / Tool | Hindsight | cascadeflow | Best for |
| :---: | :---: | :---: | :---: |
| **OpenClaw** | ✅ docs.hs/openclaw | ✅ docs.cf/openclaw | Combined projects |
| **CrewAI** | ✅ docs.hs/crewai | ✅ docs.cf/crewai | Multi-agent |
| **Vercel AI SDK** | ✅ docs.hs/ai-sdk | ✅ docs.cf/vercel-ai | TS server agents |
| **Pydantic AI** | ✅ docs.hs/pydantic-ai | ✅ docs.cf/pydantic-ai | Python type-safe |
| **LiteLLM** | ✅ docs.hs/litellm | ✅ 100+ providers | Provider breadth |
| **LangChain/LangGraph** | — | ✅ docs.cf/langchain | Python chains |
| **Google ADK** | — | ✅ docs.cf/google-adk | Google stack |
| **OpenAI Agents SDK** | — | ✅ docs.cf/openai-agents | OpenAI-native |
| **n8n** | — | ✅ docs.cf/n8n | No-code workflows |
| **Claude Code** | ✅ docs.hs/claude-code | ✅ via gateway | Coding agents |

   
Full integration docs: [docs.cascadeflow.ai/integrations/overview](http://docs.cascadeflow.ai/integrations/overview)  |  [hindsight.vectorize.io/integrations](http://hindsight.vectorize.io/integrations)

 

**Free & Open-Source Model Providers**

You do not have to spend money on API credits. Both products support free and self-hosted model providers out of the box. HuggingFace gives you access to thousands of open-source models on a free inference tier. Ollama lets you run models completely locally. Groq is fast and has a generous free tier. Combine any of these with cascadeflow's budget enforcement and Hindsight's memory layer.

 

| Provider | Cost | Hindsight | cascadeflow | Notes |
| :---- | :---- | :---- | :---- | :---- |
| Groq | Free tier | ✅ | ✅ native | Recommended starting point |
| Ollama (local) | Free (local) | ✅ | ✅ native | Zero API cost, runs on your machine |
| HuggingFace | Free tier | via Ollama / API | ✅ native | 1000s of open-source models |
| vLLM (self-hosted) | Free (self-host) | via Ollama compat. | ✅ native | Best for GPU-rich setups |
| OpenAI / Anthropic | Paid | ✅ | ✅ native | Combine w/ cascadeflow budget caps |
| 100+ via LiteLLM | Varies | ✅ LiteLLM native | ✅ via LiteLLM | Azure, Bedrock, Cohere, Mistral, etc. |

   
For HuggingFace with Hindsight: use an OpenAI-compatible endpoint or route via Ollama. For cascadeflow: HuggingFace is a native provider — pip install cascadeflow\[huggingface\] or configure via the providers guide at docs.cascadeflow.ai/developers/providers-and-presets.

# **How to Pick a Winning Project**

The difference between a forgettable hackathon demo and one that makes judges (and recruiters) pay attention comes down to three things:

**1\. Solve a Real Business Problem**

The strongest projects target a workflow that actual companies struggle with. Ask yourself: “Would someone pay $50/month for this?” If the answer is yes, you are on the right track.

**Bad:** *“An AI that remembers your favorite color.”*

**Good:** *“An AI sales assistant that remembers every objection a prospect raised across calls and drafts personalized follow-ups.”*

Think about the repetitive, knowledge-heavy tasks in real jobs. The ones where people say “I wish someone would just remember all of this for me.” That is your opportunity.

**2\. Make Memory and/or Runtime Intelligence the Star**

Your project should make Hindsight’s memory layer and/or cascadeflow’s runtime intelligence central and visible. The best projects will show a clear before/after: without the technology the agent is generic; with it, the agent becomes dramatically better.

Some ways to make this shine:

* Show the agent improving its responses over multiple interactions

* Have it recall context from days or weeks ago

* Let it learn user preferences and adapt its behavior

* Produce a full audit trail of every decision your agent made (model selected, rationale, cost, latency)

* Show a compliance gate routing sensitive inputs to approved models only

* Build an agent that stays within a budget across 50 runs, not just one 

* Show cost dropping 50%+ after adding cascadeflow routing

**3\. Think Like a Demo**

You have limited time to impress judges. Pick a use case where the value is obvious within 60 seconds of watching. The best hackathon projects tell a story: “Here is the problem. Here is the agent solving it. Watch how it gets smarter / cheaper / more controlled.” 

**Note:** If you’re using a coding agent like Claude Code or Codex, a good resource to help you flesh out a good project is GStack by Gary Tan \- the CEO of YCombinator. Install the skill using the instructions in the repo then use **/gstack-office-hours** in your coding agent to help flesh out your idea. Who knows? Maybe your hackathon project will turn into the next big thing at YCombinator\!

# **Project Ideas that Show a Real Problem**

The best submissions combine three things: an agent that remembers, an agent that can be explained, and a use case worth building. The challenges below are your three building blocks.

**Challenge 1: Show that your agent learns** *(Hindsight)* Demonstrate persistent memory across sessions. Show a concrete moment where past experience changed present behavior — interaction 1 is generic, interaction 5 is different because of what happened before. That delta is the demo.

**Challenge 2: Show that your agent runs smarter** *(cascadeflow)* Add runtime intelligence inside your agent loop. This could mean enforcing a token budget and showing graceful degradation, routing to faster or cheaper models based on task complexity, cutting latency by trying an efficient model first and escalating only when quality requires it, or producing a full audit trail of every decision (without capturing user data). Pick the angle that fits your project. Show the before and after.

**Challenge 3: Solve a real problem** Ask yourself: would someone pay $50/month for this? Pick a domain from the ideas below — or bring your own. Avoid student-centric projects. Think startup, not homework.

---

**Project Ideas**

| Domain | Agent Idea |
| :---- | :---- |
| Sales | Deal Intelligence Agent |
| Sales | Outbound Prospecting Agent |
| Sales | Proposal & RFP Agent |
| Marketing | Content Strategy Agent |
| Marketing | Social Media Engagement Agent |
| Engineering | Incident Response Agent |
| Engineering | Code Review Agent |
| Engineering | CI/CD Pipeline Agent |
| Support | Customer Support Agent |
| Support | Contract Review Agent |
| Compliance | Regulated Data Processing Agent |
| Compliance | AI Decision Audit Agent |
| Product | User Feedback Synthesizer |
| Product | Competitive Intelligence Agent |
| Product | Meeting Prep Agent |

For inspiration on what makes ideas worth building: [https://github.com/msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)

# **How to Make Your Project Stand Out**

**Tell a Story with Your Demo**

Don’t just show features. Walk through a realistic scenario: “Imagine you are a sales rep on your fifth call with a prospect...” Make the judges feel the problem before you show the solution.

**Show the Learning Curve**

The most compelling Hindsight demos show the agent getting noticeably better. Interaction 1: generic. Interaction 5: personalized. Interaction 20: feels like it knows you. That progression is what makes memory-powered agents exciting.

**Show the Cost Curve**

The most compelling cascadeflow demos show real numbers. “Before: $0.12 per query. After: $0.02 per query, same quality.” Or: “Our agent hit its $1 budget and gracefully switched to local models instead of crashing.” Engineers love concrete metrics.

**Build Something You Would Put on LinkedIn Tomorrow**

If you wouldn’t proudly post about it, rethink your approach. The best hackathon projects get written up as case studies, attract followers, and start conversations. Aim for that.

**Keep the Scope Tight**

You have limited time. A polished agent that does one thing brilliantly beats a sprawling prototype that does five things poorly. Pick one workflow, one persona, one clear value proposition and nail it.

**Use Real (or Realistic) Data**

Agents that operate on toy data feel like toys but real data isn’t always easy to come by. A good solution is to generate synthetic data, but make it realistic. Give your customers real-sounding names, your deals real-sounding numbers, your incidents real-sounding error logs.

# **Important Rules**

All teams must ALSO share their project based on challenges from the official content guide.

**Content Guide:** Hackathon Content Guide (see official link)

Your project must clearly demonstrate how Hindsight memory and/or cascadeflow runtime intelligence is used in your solution.

# **Submission Requirements**

Each team must submit:

* **GitHub Repository** with clean, documented code

* **Demo Video** showing the agent in action

* **Live Project Demo** to judges

* **Content deliverables:** All team members must complete an Article, Social Media post, and Video as described in the content guide

* **Explanation of how Hindsight memory and/or cascadeflow runtime intelligence is used** in your solution

# **Judging Criteria**

| Criteria | Weight | What Judges Are Looking For |
| :---- | :---- | :---- |
| Innovation | **30%** | Is this a fresh take on a real problem? Does it go beyond obvious chatbot territory? |
| Use of Hindsight & cascadeflow | **25%** | Is memory and/or runtime intelligence central to the value proposition? Does the agent clearly improve over time or demonstrate intelligent cost/model control? |
| Technical Implementation | **20%** | Is the code clean, well-architected, and functional? Does it handle edge cases? |
| User Experience | **15%** | Is the agent intuitive to interact with? Does the demo flow tell a compelling story? |
| Real-world Impact | **10%** | Could this solve a genuine problem for real users? Is there a path to actual adoption? |

*Now stop reading and start building.*

*The best way to learn AI agents is to ship one.*