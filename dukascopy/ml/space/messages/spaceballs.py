"""
===============================================================================
File:         spaceballs.py
Theme:        Spaceballs
Description:  Comb-heavy, jam-filled strings for the Druidia sectors.
===============================================================================
"""

STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "🛸 [Spaceball One]: Taking {universe} to Ludicrous Speed for {symbol}! {start} -> {end}",
    "SPACE_BIG_BANG": "💥 [Dark Helmet]: I see your Schwartz is as big as mine! {dims} dimensions normalized.",
    "SPACE_THERMAL_HOT": "🔥 [Radar]: Raspberry! Only one man would dare give me the raspberry: ({temp}°C).",
    "SPACE_THERMAL_COLD": "❄️ [Radar]: Liquid Schwartz levels stabilized ({temp}°C). Resume the search!",
    "COMET_ORBIT": "📋 [Perri-air]: Sniffing '{name}'. Freshness duration: {size}",
    "COMET_DISSIPATE": "📉 [De-Rez]: Program '{name}' has gone from suck to blow. Terminated.",
    "COMET_EJECTION_ERROR": "❌ [Error]: We can't stop! It's too dangerous! We have to slow down first! {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🏦 [Merchandising]: Spaceballs the Neural Network initialized on {device}!",
    "SINGULARITY_LENS": "👓 [Yogurt]: Use the Schwartz, Lonestarr! {lens} optics engaged.",
    "SPACE_MATERIALIZING": "📦 [Teleport]: Beaming up {name} for {symbol}. Watch the ears!",
    "COSMIC_NORMALIZATION": "🌀 [Comb]: We ain't found ship! Standardizing the bitstreams...",
    "REDSHIFT_NORMALIZE": "🌀 [Grid]: Keep combing the desert! Relative coordinates applied.",
    "GRAVITATIONALLENS_INIT": "👓 [The Schwartz]: Piercing the veil. GravitationalLens looking for the princess.",
    "STANDARDEYE_INIT": "👓 [The Schwartz]: I bet she's a Druish Princess! StandardEye engaged.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "🚀 [Ludicrous Speed]: Light speed is too slow. We're going straight to Plaid!",
    "FLIGHT_GEN_START": "🚀 [Bridge]: Starting Operation Vacation {gen}/{total}",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Generation {gen} Merchandising Report] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   YOGURT_LEVEL: Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   DRUID_LUCK:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   SIGNAL_JAM:   Total Sigs {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   PRESIDENT_SKROOB_SIGS: {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Win]: What's the matter, Colonel Sandurz? Chicken? {f1:.4f} beats {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Desert]: Still combing... Stagnation: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Best Schwartz: {f1:.4f} (Gen {gen})",
    "FLIGHT_REJECTED": "⚠️ [Spaceball One]: F1 {f1:.4f} rejected. Signal density ({sigs}) is absolute zero ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Desert]: We ain't found ship: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [Self-Destruct]: 10-9-8-6... I can't even count! Resetting the universe...",
    "FLIGHT_RAD_DEEP": "☢️  [Plaid]: Going past Ludicrous! Mutation levels at 60%...",
    "FLIGHT_RAD_INJECT": "☢️  [Liquid]: Injecting the Schwartz into 40% of the population...",
    "FLIGHT_COMPLETE": "\n🏁 [The End]: Spaceballs: The Sequel! Flight path complete.",
    "FLIGHT_BEST_RESULT": "🥇 [The Schwartz]: Gen {gen} achieved F1 {f1:.4f}. May the Schwartz be with you!",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Radar]: Found 'em! Model {idx} is at: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Radar]: I've lost the bleeps, I've lost the sweeps, and I've lost the creeps!",
    "DIAG_UNAVAILABLE": "❌ [Error]: The tape! You're looking at now, sir. Tensor unavailable.",
    "GENE_VITALITY_HEADER": "\n🧬 [Merchandise Catalog Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Market Price: {score:.4f}",
    "CLEANUP_START": "\n🧹 [MegaMaid]: Changing from suck to blow...",
    "CLEANUP_END": "✅ [MegaMaid]: Druidia is empty. Singularity stable.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🌌 [Omaha]: Launching Spaceball One for {symbol}...",
    "SPACE_BOUNDARY": "🚧 [Boundary]: Who made this man a gunner? Boundary at {date}!",
    "DATA_AUDIT_TARGET": "📊 [Audit]: Target Princess: {target}",
    "DATA_AUDIT_BARS": "📊 [Audit]: Total Space-bars: {count}",
    "DATA_AUDIT_SIGS": "📊 [Audit]: Schwartz signals found: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [Error]: I'm surrounded by Assholes! '{target}' not found!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Clean]: Comb the strings! Removed {count} polluted dimensions.",
    "SPACE_DISCOVERY": "✅ [Success]: Found {count} Druid dimensions.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [Statue]: Yogurt's blessing. Champion (F1={f1:.4f}) pinned to Slot 1",
    "CORE_FIX_INDIVIDUAL": "🔧 [Maintenance]: Repairing the Winnebago for individual {i}",
    "CORE_CHAMP_LOST": "  ⚠️ [Crisis]: We've lost the bleeps! Restoring Champion to position 1",
    "PULSAR_NEW_RECORD": "🔥 [Market]: Spaceballs the High-Water Mark: {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Merchandise]: Saving the best model (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🛑 [Abort]: Out of coffee! Save aborted. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Error]: My brains are going into my feet! {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Result]: Winner Ejected to Video. Features: {features} | F1: {f1:.4f}",
    "PULSAR_CHUNK_LOG": "Chunk {chunk} | Plaid: {max_p:.3f} | Targets: {targets:.0f} | Fired: {fired:.0f}",
    
    # Audit & Error States
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Audit]: MegaMaid Sector Integrity Report",
    "ATMOSPHERIC_WASTE": "🚫 [Waste]: {count} dimensions went from suck to blow.",
    "NOSTRING_POLLUTION": "✅ [Audit]: No raspberry jam detected in requested features.",
    "MATTER_CHECK_SUCCESS": "💎 [Solid]: All {count} dimensions are Druish (0 NaNs).",
    "VOID_REPORT_WARNING": "⚠️ [Void]: {count} dimensions contain industrial strength vacuum holes.",
    "DATA_DENSITY_CRITICAL": "🚨 [Critical]: {count} columns are Assholes! Data loss > 50%!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [Error]: No air! Open the canned atmosphere first.",
    "INITIALIZATION_FAILURE": "❌ [Error]: Ship hit the self-destruct: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Gen {gen} Summary] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Bleeps {sigs} | Density {density:.4%}"
}