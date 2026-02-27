"""
===============================================================================
File:         buffett.py
Theme:        Warren Buffett / Value Investing
Description:  Prudent, long-term oriented strings for the Oracle of Omaha.
===============================================================================
"""

STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "📈 [Omaha]: Opening the ledger for {universe} ({symbol})... {start} -> {end}",
    "SPACE_BIG_BANG": "💰 [Berkshire]: Capital allocation successful. {dims} assets normalized for our portfolio.",
    "SPACE_THERMAL_HOT": "🔥 [Margin]: Market euphoria detected ({temp}°C). Be fearful while others are greedy...",
    "SPACE_THERMAL_COLD": "❄️ [Margin]: Market panic subsided ({temp}°C). Margin of safety restored. Buying the dip.",
    "COMET_ORBIT": "📋 [Due Diligence]: Auditing '{name}'. Economic moat width: {size}",
    "COMET_DISSIPATE": "📉 [Divest]: Program '{name}' lacked a durable competitive advantage. Sold.",
    "COMET_EJECTION_ERROR": "❌ [Audit Error]: Critical failure in asset liquidation '{name}': {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🏦 [Treasury]: Intelligent Investor Core active on {device}. Circle of competence defined.",
    "SINGULARITY_LENS": "👓 [Moat]: Refining our view. {lens} perspective applied to avoid permanent loss of capital.",
    "SPACE_MATERIALIZING": "📦 [Acquisition]: Purchasing {name} for User:{symbol}. Adding to the conglomerate...",
    "COSMIC_NORMALIZATION": "🌀 [Accounting]: Standardizing the balance sheet. Adjusting for GAAP...",
    "REDSHIFT_NORMALIZE": "🌀 [Valuation]: Discounting future cash flows. Z-Score normalization applied.",
    "GRAVITATIONALLENS_INIT": "👓 [Intrinsics]: Piercing the market noise. GravitationalLens finding intrinsic value.",
    "STANDARDEYE_INIT": "👓 [Intrinsics]: Reading the annual report. StandardEye resolving hidden assets.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "🚜 [Farm]: Planting the seeds. Starting the compounding cycle...",
    "FLIGHT_GEN_START": "🚜 [Farm]: Commencing Fiscal Period {gen}/{total}",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Period {gen} Shareholder Letter] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   ROE:         Avg {avg_f1:.4f} | Peak {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   DIVIDEND:    Avg {avg_prec:.4f} | Peak {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   TURNOVER:    Aggregate Sigs {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   CEO_PERFORMANCE: {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Record]: New Alpha discovered! {f1:.4f} beats previous index {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Waiting]: No 'fat pitches' lately. Staying in the dugout: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current High-Water Mark: {f1:.4f} (Period {gen})",
    "FLIGHT_REJECTED": "⚠️ [Reject]: F1 {f1:.4f} is a cigar butt. Yield ({sigs}) below hurdle rate ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Waiting]: Cash position increasing: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [Bankruptcy]: TOTAL LIQUIDATION. Business model failed. Reallocating capital...",
    "FLIGHT_RAD_DEEP": "☢️  [Restructure]: Massive corporate overhaul! Mutation levels at 60%...",
    "FLIGHT_RAD_INJECT": "☢️  [Venture]: Injecting speculative capital into 40% of the portfolio...",
    "FLIGHT_COMPLETE": "\n🏁 [Omaha]: Market closed. Flight path complete.",
    "FLIGHT_BEST_RESULT": "🥇 [Grandmaster]: Period {gen} achieved F1 {f1:.4f}. Buy and hold.",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Audit]: Manager {idx} identified opportunities at: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Audit]: Manager {idx} stayed on the sidelines (0 signals).",
    "DIAG_UNAVAILABLE": "❌ [Error]: Ledger corrupted. Financial statements unavailable.",
    "GENE_VITALITY_HEADER": "\n🧬 [Durable Moat Features Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Book Value: {score:.4f}",

    # Thermal & Physics (Synchronized with Spacey)
    "THERMAL_SPIKE": "🔥 [Margin]: Market euphoria detected ({temp}°C). Be fearful while others are greedy...",
    "THERMAL_RESUME": "❄️ [Margin]: Market panic subsided ({temp}°C). Margin of safety restored.",
    "CLEANUP_START": "\n🧹 [Audit]: Selling off the non-core assets...",
    "CLEANUP_END": "✅ [Audit]: Conglomerate stable. Books are balanced.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "📈 [Omaha]: Preparing {symbol} for long-term growth...",
    "SPACE_BOUNDARY": "🚧 [Boundary]: Reached the fiscal cliff at {date}. No more data in the ledger.",
    "DATA_AUDIT_TARGET": "📊 [Audit]: Target Moat: {target}",
    "DATA_AUDIT_BARS": "📊 [Audit]: Total Quarterly Reports: {count}",
    "DATA_AUDIT_SIGS": "📊 [Audit]: Undervalued entries found: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [Audit]: Fundamental '{target}' missing from the balance sheet!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Audit]: Written off {count} string-polluted 'goodwill' dimensions.",
    "SPACE_DISCOVERY": "✅ [Audit]: Discovered {count} high-quality assets.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [Insurance]: Float secured. Champion (F1={f1:.4f}) locked in as CEO",
    "CORE_FIX_INDIVIDUAL": "🔧 [Audit]: Correcting accounting error for individual {i}",
    "CORE_CHAMP_LOST": "  ⚠️ [Crisis]: CEO fired! Restoring from the board-approved backup...",
    "PULSAR_NEW_RECORD": "🔥 [Market]: Outperforming the S&P 500: {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Archives]: Documenting winning strategy (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🛑 [Archives]: Acquisition rejected by the board. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Error]: Failed to extract economic physics: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Result]: Winner Acquired. Moat Features: {features} | F1: {f1:.4f} | Precision: {prec:.4f}",
    "PULSAR_CHUNK_LOG": "Portfolio {chunk} | Yield: {max_p:.3f} | Assets: {targets:.0f} | Buys: {fired:.0f} | F1: {f1:.4f}",
    
    # Hale-Bopp & Advanced Normalization
    "HALEBOPP_EJECT": "☄️ [Exit]: Long-term target reached. Delivering payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [Audit]: Materialized {count} elite economic dimensions.",
    "COSMIC_NORMALIZATION": "🔭 [Audit]: Applying Prudent Normalization (Value & Kinematics)...",

    # Audit & Error States
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Audit]: Asset Integrity Report",
    "ATMOSPHERIC_WASTE": "🚫 [Waste]: {count} junk-bond dimensions dropped (Non-Numeric/Strings).",
    "NOSTRING_POLLUTION": "✅ [Audit]: No creative accounting found in requested features.",
    "MATTER_CHECK_SUCCESS": "💎 [Solid]: All {count} dimensions have a high margin of safety (0 NaNs).",
    "VOID_REPORT_WARNING": "⚠️ [Void]: {count} dimensions contain accounting black holes (NaNs)",
    "DATA_DENSITY_CRITICAL": "🚨 [Critical]: {count} columns are technically insolvent (>50% empty)!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [Error]: No capital found. Fund the account and ignite the universe first.",
    "INITIALIZATION_FAILURE": "❌ [Error]: Market crash during init: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Period {gen} Earnings] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Entries {sigs} | Density {density:.4%}"
}