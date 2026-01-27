


**Status: Upstream datafeeds are currently not updating.**

I am monitoring the situation. The dump.py script has been re-added, and a randomized startup delay was introduced in run.sh to reduce synchronized load. Please update.

Note on feed stability and longer-term direction

The project is still in an active development phase. During this stage, occasional upstream feed interruptions are expected and actively monitored.

As the system matures, the long-term solution will be to transition toward SLA-backed, enterprise-grade data feeds. At the moment, the software does not yet require that level of guaranteed uptime, but this is an anticipated next step.

My current expectation is that within the next ~3 months, moving toward more stable, SLA-covered feeds will make sense. Until then, the focus remains on development, correctness, and improving resilience to upstream pauses.

I will continue to be transparent when outages occur and when changes are made.