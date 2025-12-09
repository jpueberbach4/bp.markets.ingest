## First Run & Terms Acceptance

On first execution, you'll see our Terms of Service. Here's why:

### The Context:

- **Viral Growth**: 2,000+ clones in 13 days
- **Enterprise Scale**: Parquet enables professional-grade usage  
- **Responsibility**: With scale comes need for governance

### This Ensures:

- The project remains available for legitimate uses
- Everyone respects data provider terms
- Educational/research access continues uninterrupted

This is standard practice for successful data tools. The terms
protect you, us, and ensure the tool's long-term sustainability.

### Additional information on what happened

On December 6th, I reviewed the clone statistics and noticed a sharp increase in usage. I'm aware of how useful this tool is—I rely on it myself—but I also knew that many requests were overwhelming the servers, and that Dukascopy had likely already noticed the traffic.

After checking their website's Terms of Service, I realized we needed to introduce guardrails to protect Dukascopy's interests and infrastructure. Several issues in the code required immediate attention:

- Excessive power of --select "*/*" \
\
I realized the exporter was far too powerful. With a single command, someone could dump their entire data stack into a Parquet hive. \
I removed this capability to reduce the potential attack surface.

- Lack of rate limiting \
\
The download module had no rate limiting, which meant it could unintentionally hammer their servers—especially with so many users. To address this, I added a rate_limit_rps parameter and documented the formula for calculating a responsible request rate based on how many hours a user wants to spend on a download.

- Missing legal framework \
\
Most importantly, we needed clearer legal boundaries to demonstrate our responsibility in protecting Dukascopy's interests, especially regarding redistribution. Our goal is not to compete with Dukascopy, but to complement their service by providing an analysis tool for educational, research, and private use.

The demand for this tool turned out to be very high, judging by the rapid growth in clones. After implementing the guardrails above, I reached out to Dukascopy on December 7th to seek formal approval. They responded positively December 8th.

You are now using a tool that has been reviewed and sanctioned. If the initial, very strict legal warning startled you, we apologize—but those steps were necessary to secure official approval.