"""
===============================================================================
File:         wonderland.py
Theme:        Alice in Wonderland
Description:  Whimsical and nonsensical strings for the rabbit hole.
===============================================================================
"""

STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "🍄 [Wonderland]: Shrinking {universe} for {symbol}... {start} -> {end}",
    "SPACE_BIG_BANG": "🃏 [Queen]: Off with their heads! {dims} dimensions painted red and normalized.",
    "SPACE_THERMAL_HOT": "☕ [Tea Party]: It's always tea-time! Radiation spike ({temp}°C).",
    "SPACE_THERMAL_COLD": "🧥 [Alice]: Temperature reached equilibrium ({temp}°C). Fitting through the tiny door.",
    "COMET_ORBIT": "🐰 [White Rabbit]: Late for a very important date! Tracking {name}. Tail: {size}",
    "COMET_DISSIPATE": "🌬️ [Chesire]: Program {name} vanished, leaving only a grin.",
    "COMET_EJECTION_ERROR": "❌ [Jabberwocky]: Beware the Jubjub bird! Extraction error for {name}: {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🌀 [Rabbit Hole]: Falling onto {device}. Don't forget your umbrella.",
    "SINGULARITY_LENS": "🔭 [Looking Glass]: Stepping through. {lens} perspective active.",
    "SPACE_MATERIALIZING": "🧁 [Eat Me]: Materializing {name} for {symbol}. Growing larger...",
    "COSMIC_NORMALIZATION": "🔭 [Space]: Applying Logic of the Absurd (Redshift & Kinematics)...",
    "REDSHIFT_NORMALIZE": "🌌 [Physics]: Six impossible things before breakfast. Z-Score normalization.",
    "GRAVITATIONALLENS_INIT": "👁️ [Caterpillar]: Who... are... YOU? GravitationalLens resolving hidden matter.",
    "STANDARDEYE_INIT": "👁️ [Dormouse]: Piercing the void. StandardEye resolving hidden matter.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "🎩 [Mad Hatter]: Firing up the MilleniumFalcon. We're all mad here!",
    "FLIGHT_GEN_START": "🚀 [Flight]: Commencing Chapter {gen}/{total}",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Chapter {gen} Summary] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   F1:         Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   Precision:  Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   Activity:   Total Rabbits {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   Winner Sigs: {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Flight]: A Golden Key! {f1:.4f} beats the previous {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Flight]: Stuck at the tea party. Stagnation: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Best F1: {f1:.4f} (Chapter {gen})",
    "FLIGHT_REJECTED": "⚠️ [Flight]: F1 {f1:.4f} rejected. Not enough jam ({sigs}) for the King ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Flight]: Stagnation: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [Flight]: HOUSE OF CARDS. Stagnation reached. Resetting Wonderland...",
    "FLIGHT_RAD_DEEP": "☢️  [Flight]: DEEP MADNESS. Intensifying potion (60% mutation)...",
    "FLIGHT_RAD_INJECT": "☢️  [Flight]: Injecting 'Drink Me' potion into 40% of population...",
    "FLIGHT_COMPLETE": "\n🏁 [Flight]: Waking up from the dream.",
    "FLIGHT_BEST_RESULT": "🥇 [Best Result]: Chapter {gen} achieved F1 {f1:.4f}",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Diagnostic]: Model {idx} found dodo birds at: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Diagnostic]: Model {idx} found no tea here.",
    "DIAG_UNAVAILABLE": "🔍 [Diagnostic]: Looking-glass tensor unavailable. Check Singularity output.",
    "GENE_VITALITY_HEADER": "\n🧬 [Wonderland Vitality Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Score: {score:.4f}",

    # Thermal & Physics Updates
    "THERMAL_SPIKE": "🔥 [Space]: Radiation spike ({temp}°C). Moving to the dark side of the mushroom.",
    "THERMAL_RESUME": "🛰️ [Space]: Thermal equilibrium reached ({temp}°C). Main drive re-engaged.",
    "CLEANUP_START": "\n🛰️ [Flight]: Shuffling the deck...",
    "CLEANUP_END": "✅ [Flight]: Cleanup complete. The Queen is satisfied.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🌌 [Space]: Igniting MilkyWay for {symbol}...",
    "SPACE_BOUNDARY": "🌌 [Space]: Boundary at {date}. You've reached the edge of the map.",
    "DATA_AUDIT_TARGET": "📊 [Data Audit]: Target Column: {target}",
    "DATA_AUDIT_BARS": "📊 [Data Audit]: Total Bars: {count}",
    "DATA_AUDIT_SIGS": "📊 [Data Audit]: Signals found: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [Space Error]: Target '{target}' is as missing as Alice's cat!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Space]: Swept away {count} nonsensical string dimensions.",
    "SPACE_DISCOVERY": "✅ [Space]: Discovered {count} valid paths through the woods.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [Singularity]: Quantum Lock: Champion (F1={f1:.4f}) pinned to Slot 1",
    "CORE_FIX_INDIVIDUAL": "🔧 Post-processing fix for playing-card {i}",
    "CORE_CHAMP_LOST": "  ⚠️ [Evolution]: Champion lost! Restoring to position 1",
    "PULSAR_NEW_RECORD": "🔥 [Evolution]: New High-Water Mark: {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Singularity]: Saving pending best model with F1={f1:.4f}, Precision={prec:.4f}",
    "PULSAR_SAVE_ABORT": "🛑 [Singularity]: Save aborted. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Singularity]: Failed to extract Redshift physics: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Singularity]: Atomic Winner Ejected. Features: {features} | F1: {f1:.4f} | Precision: {prec:.4f}",
    "PULSAR_CHUNK_LOG": "Chunk {chunk} | MaxP: {max_p:.3f} | Targets: {targets:.0f} | Fired: {fired:.0f} | F1: {f1:.4f}",
    
    # Hale-Bopp & Advanced Normalization
    "HALEBOPP_EJECT": "☄️ [Hale-Bopp]: Perihelion reached. Ejecting payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [Hale-Bopp]: Materialized {count} elite dimensions.",

    # Audit & Error States
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Space]: Dimension Audit Report",
    "ATMOSPHERIC_WASTE": "🚫 [Atmospheric Waste]: {count} dimensions dropped (Non-Numeric/Strings)",
    "NOSTRING_POLLUTION": "✅ No string pollution detected in requested features.",
    "MATTER_CHECK_SUCCESS": "💎 Matter Check: All {count} dimensions are solid (0 NaNs).",
    "VOID_REPORT_WARNING": "⚠️ [Void Report]: {count} dimensions contain holes (NaNs)",
    "DATA_DENSITY_CRITICAL": "🚨 CRITICAL: {count} columns are more than 50% empty!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [Space]: No matter found. Paint the roses first.",
    "INITIALIZATION_FAILURE": "❌ [Init Error]: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Gen {gen} Summary] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   Precision:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   Activity:    Total Sigs {sigs} | Density {density:.4%}"
}