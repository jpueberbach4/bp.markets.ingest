"""
===============================================================================
File:         matrix.py
Theme:        The Matrix
Description:  Green-on-black digital rain. There is no spoon.
===============================================================================
"""

STRING_TABLE = {
    # System & Simulation Entry
    "SPACE_IGNITE": "🕶️ [Matrix]: Jacking into {universe} for {symbol}... {start} -> {end}",
    "SPACE_BIG_BANG": "📟 [Operator]: Residual self-image resolved. {dims} dimensions normalized into the construct.",
    "SPACE_THERMAL_HOT": "🔥 [System]: Agent detected. Heat signature rising ({temp}°C). Jumping to secondary hardline...",
    "SPACE_THERMAL_COLD": "📞 [Operator]: Trace cleared ({temp}°C). Re-inserting into the simulation.",
    "COMET_ORBIT": "📡 [Signal]: Tracking white rabbit '{name}'. Signal strength: {size}",
    "COMET_DISSIPATE": "🕶️ [Matrix]: Program '{name}' has been deleted by the system.",
    "COMET_EJECTION_ERROR": "❌ [Error]: Glitch in the Matrix during '{name}' extraction: {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🌀 [TheOne]: Construct initialized on hardware: {device}",
    "SINGULARITY_LENS": "👁️ [Oracle]: Seeing beyond the code. {lens} filter engaged.",
    "SPACE_MATERIALIZING": "📞 [Operator]: Loading {name} for {symbol} into the Construct...",
    "COSMIC_NORMALIZATION": "🌀 [Matrix]: Stripping the simulation. Standardizing bitstreams...",
    "REDSHIFT_NORMALIZE": "🌀 [Matrix]: Applying relative coordinate shift. Z-Score normalization applied.",
    "GRAVITATIONALLENS_INIT": "👁️ [Oracle]: Piercing the veil. GravitationalLens resolving hidden code.",
    "STANDARDEYE_INIT": "👁️ [Oracle]: Viewing the raw code. StandardEye resolving hidden code.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "📟 [Operator]: I'm in. Starting the evolutionary loop...",
    "FLIGHT_GEN_START": "📟 [Operator]: Executing iteration {gen}/{total}...",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Iteration {gen} Stream Analysis] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   F1_VALUE:    Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   ANOMALIES:   Total Sigs {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   THE_ONE_SIGS: {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Operator]: We have a winner! {f1:.4f} breaks the previous record of {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Matrix]: Déjà vu detected. No improvement. Stagnation: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Alpha Individual: {f1:.4f} (Iteration {gen})",
    "FLIGHT_REJECTED": "⚠️ [Sentinel]: F1 {f1:.4f} purged. Signal density ({sigs}) fails system requirements ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Matrix]: Déjà vu counter: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [System]: Smith Protocol initiated. Mass deletion. Resetting construct...",
    "FLIGHT_RAD_DEEP": "☢️  [System]: Re-writing the source code. Mutation levels at 60%...",
    "FLIGHT_RAD_INJECT": "☢️  [System]: Injecting glitches into 40% of the population...",
    "FLIGHT_COMPLETE": "\n🏁 [Operator]: Connection terminated. Flight path complete.",
    "FLIGHT_BEST_RESULT": "🥇 [The One]: Iteration {gen} achieved F1 {f1:.4f}. Follow the white rabbit.",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Scan]: Program {idx} identified anomalies at: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Scan]: Program {idx} found zero anomalies in the code.",
    "DIAG_UNAVAILABLE": "❌ [Error]: Data stream interrupted. Tensor unavailable.",
    "GENE_VITALITY_HEADER": "\n🧬 [Source Code Vitality Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Vitality: {score:.4f}",

    # Thermal & Physics (Missing Strings Added)
    "THERMAL_SPIKE": "🔥 [System]: Agent detected. Heat signature rising ({temp}°C). Jumping to secondary hardline...",
    "THERMAL_RESUME": "📞 [Operator]: Trace cleared ({temp}°C). Re-inserting into the simulation.",
    "CLEANUP_START": "\n📞 [Operator]: Knock, knock, Neo. Clearing the cache...",
    "CLEANUP_END": "✅ [Operator]: System purged. Construct stable.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🕶️ [Matrix]: Loading MilkyWay simulation for {symbol}...",
    "SPACE_BOUNDARY": "🕶️ [Matrix]: Boundary detected at {date}. There is no spoon.",
    "DATA_AUDIT_TARGET": "📊 [Audit]: Target Sequence: {target}",
    "DATA_AUDIT_BARS": "📊 [Audit]: Total Bitstreams: {count}",
    "DATA_AUDIT_SIGS": "📊 [Audit]: Anomalies found: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [Error]: Target sequence '{target}' not found in the source code!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Matrix]: Wiping {count} dimensions of string-based noise.",
    "SPACE_DISCOVERY": "✅ [Matrix]: Identified {count} valid code paths.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [TheOne]: Quantum Lock: Champion (F1={f1:.4f}) cached in the Source.",
    "CORE_FIX_INDIVIDUAL": "🔧 [Repair]: Patching bit-collision for program {i}",
    "CORE_CHAMP_LOST": "  ⚠️ [Alert]: The One has been deleted! Restoring from back-up...",
    "PULSAR_NEW_RECORD": "🔥 [Evolution]: New High-Water Mark reached: {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Operator]: Exporting optimized program (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🛑 [Operator]: Export failed. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Error]: Failed to extract Z-space physics: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Operator]: Program Ejected. Features: {features} | F1: {f1:.4f} | Precision: {prec:.4f}",
    "PULSAR_CHUNK_LOG": "Stream {chunk} | MaxProb: {max_p:.3f} | Anomalies: {targets:.0f} | Fired: {fired:.0f} | F1: {f1:.4f}",
    
    # Hale-Bopp & Advanced Normalization
    "HALEBOPP_EJECT": "🚁 [Operator]: Hardline reached. Exporting program payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [Oracle]: Extracted {count} core logic patterns from the source.",
    "COSMIC_NORMALIZATION": "🔭 [Oracle]: Calibrating the Construct kinematics and bitstream flow...",

    # Audit & Error States
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Audit]: Dimension Integrity Report",
    "ATMOSPHERIC_WASTE": "🚫 [Noise]: {count} string-polluted dimensions removed (Non-Numeric/Strings).",
    "NOSTRING_POLLUTION": "✅ [Clean]: No string pollution detected in the stream.",
    "MATTER_CHECK_SUCCESS": "💎 [Solid]: All {count} dimensions are optimized (0 NaNs).",
    "VOID_REPORT_WARNING": "⚠️ [Void]: {count} dimensions contain null bytes (NaNs)",
    "DATA_DENSITY_CRITICAL": "🚨 [Critical]: {count} code columns are more than 50% empty!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [Error]: Construct is empty. Jack in first.",
    "INITIALIZATION_FAILURE": "❌ [Error]: System failure: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Iteration {gen} Summary] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Anomalies {sigs} | Density {density:.4%}"
}