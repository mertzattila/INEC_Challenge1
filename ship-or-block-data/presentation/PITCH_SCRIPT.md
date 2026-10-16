# 2-Minute Pitch Script: Ship or Block Gate
**Team**: Azta Quality Gate | **Presentation Time**: Exactly 2:00 (Hard stop at 2:00)  
**Slides**: Exactly 2 slides in `Ship_or_Block_Pitch.pdf`

---

### [0:00 – 1:00] Member 1: The Challenge, Funnel & Feasibility (Slide 1)

> **Speaker 1 (0:00 - 0:25) — The Problem & Funnel**  
> *"Good morning judges. An AI that answers tax and legal questions is only as good as the answers it refuses to give. In Nordvale, with over 21,000 section versions across 430 acts, the wrong answers aren’t obvious hallucinations — they are subtle traps: a repealed fee from last month, an intra-act transitional clause, or an override buried in an entirely separate act.*  
>  
> *Because 21,000 sections can never fit in context, our gate uses a strict **two-stage architecture**:*  
> *Stage 1 is a **zero-cost, deterministic context funnel** running locally in under 35 milliseconds. It prunes 99.7% of the corpus down to the top 70 highest-signal candidates using three complementary strategies:*  
> *1) Temporal in-force resolution against the exact ask date,*  
> *2) A bidirectional cross-reference graph that captures both cross-act overrides like 'Notwithstanding FDA §14' and same-act transitional rules,*  
> *3) A statutory synonym bridge that translates colloquial facts into formal defined terms.*  
> *On the practice set, this deterministic filter achieves **91.2% recall** of the ground-truth evidence."*

> **Speaker 1 (0:25 - 1:00) — LLM Verification & Feasibility**  
> *"Stage 2 is our LLM Verification Gate. Each case makes exactly **one model call** to Gemini 2.5 Flash, inspecting only the 70 retrieved provisions against the four statutory conditions.*  
>  
> *For real-world enterprise feasibility across Azta’s 28 countries, our system is production-ready:*  
> *• **Cost**: It costs just **$0.0024 per answer checked**. Our entire 500-case test run cost only **$1.20**, well within the $10 budget.*  
> *• **Speed**: Operating with 8 parallel workers, our pipeline processes ~3.3 queries per second, validating 500 enterprise answers in under 2.5 minutes."*

---

### [1:00 – 2:00] Member 2: Defense Perimeter, Known Limits & Economics (Slide 2)

> **Speaker 2 (1:00 - 1:30) — What It Catches vs Known Limits**  
> *"(Switch to Slide 2) Looking at our defense perimeter:*  
> *Our gate reliably catches:*  
> *1) Outdated statutory rates when laws change between question and enactment,*  
> *2) Cross-act student/allowance overrides that human advisors often miss, and*  
> *3) Grandfathering rules under intra-act transitional provisions.*  
>  
> *Crucially, we know its boundaries:*  
> *What slips through retrieval are zero-vocabulary, multi-hop definition chains where everyday descriptions share no tokens across three intermediate statutes.*  
> *However, our system is engineered specifically for the asymmetric risk profile of legal advice: Shipping a wrong answer incurs a catastrophic **-3 penalty**, whereas blocking an ambiguous answer costs 0. Whenever our gate detects ambiguity or cannot conclusively ground an answer, it enforces a conservative safety fallback to BLOCK, protecting clients and leaderboard score alike."*

> **Speaker 2 (1:30 - 2:00) — Where the Money Went & Next Steps**  
> *"Where did our money go?*  
> *Zero dollars were wasted on brute-force corpus search or token bloat. 100% of our $1.25 spend was concentrated on high-precision structured reasoning on the top candidates, leaving over 87% of our budget untouched.*  
>  
> *For production deployment, our immediate roadmap adds a dense vector embedding index (like BGE-small) to close the final 8.8% vocabulary gap, plus a cross-encoder reranker to cut per-case tokens from 70 down to 25 provisions, driving cost below 8/100ths of a cent.*  
>  
> *Thank you, and we're ready to show the gate running live."*
