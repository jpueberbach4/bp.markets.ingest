"""
===============================================================================
File:         starwars.py
Theme:        Star Wars / Galactic Frontier
Description:  Hyperdrive-fueled strings for a galaxy far, far away.
===============================================================================
"""

STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "✨ [Navi-Computer]: Calculating jump to {universe} for {symbol}... {start} -> {end}",
    "SPACE_BIG_BANG": "🛰️ [Alliance]: Death Star plans decoded. {dims} sectors normalized and ready for the assault.",
    "SPACE_THERMAL_HOT": "🔥 [R2-D2]: Beep-bloop! Overheating ({temp}°C). Diverting power to shields!",
    "SPACE_THERMAL_COLD": "❄️ [Hoth]: Temperature stabilized ({temp}°C). Engines re-engaged. Echo Base, do you copy?",
    "COMET_ORBIT": "☄️ [Long Range]: Tracking Bounty Hunter '{name}'. Seismic charge range: {size}",
    "COMET_DISSIPATE": "☄️ [Deep Space]: Program '{name}' has vanished into the Outer Rim.",
    "COMET_EJECTION_ERROR": "💢 [C-3PO]: Oh dear! Technical failure in escape pod {name}: {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🌀 [The Force]: A presence felt on {device}. The core is strong with this one.",
    "SINGULARITY_LENS": "🔭 [Targeting]: Stay on target. {lens} computer engaged.",
    "SPACE_MATERIALIZING": "✨ [Hangar]: Rezzing {name} for {symbol}. Ready for takeoff.",
    "COSMIC_NORMALIZATION": "🌀 [Jedi]: Balancing the Force. Standardizing bitstreams...",
    "REDSHIFT_NORMALIZE": "🌀 [Nav]: Shifting to relative hyperspace coordinates. Z-Score normalization applied.",
    "GRAVITATIONALLENS_INIT": "👁️ [Kyber]: Piercing the Dark Side. GravitationalLens resolving hidden matter.",
    "STANDARDEYE_INIT": "👁️ [Binoculars]: Scanning the dunes. StandardEye resolving hidden matter.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "🚀 [Millennium Falcon]: Punch it, Chewie! Entering hyperspace...",
    "FLIGHT_GEN_START": "🚀 [Squadron]: Commencing Attack Run {gen}/{total}",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Generation {gen} Debrief] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   F1_POWER:    Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   ACTIVITY:    Total Signals {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   CHAMP_SIGS:  {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Council]: A new Chosen One! {f1:.4f} surpasses the old master {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Cantina]: No news from the front. Stagnation: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Grand Master F1: {f1:.4f} (Gen {gen})",
    "FLIGHT_REJECTED": "⚠️ [Empire]: F1 {f1:.4f} discarded. Signal density ({sigs}) below Imperial specs ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Cantina]: Stagnation: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [Order 66]: MASS EXTINCTION. Stagnation limit reached. Wiping the Jedi archives...",
    "FLIGHT_RAD_DEEP": "☢️  [Sith]: Unlimited Power! Intensifying mutation (60%)...",
    "FLIGHT_RAD_INJECT": "☢️  [Kamino]: Injecting genetic variation into 40% of clones...",
    "FLIGHT_COMPLETE": "\n🏁 [Rebellion]: Mission accomplished. The Force is with us.",
    "FLIGHT_BEST_RESULT": "🥇 [Skywalker]: Gen {gen} achieved F1 {f1:.4f}. Great shot, kid!",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Scanner]: Droids located at bars: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Scanner]: These are not the droids you are looking for (0 signals).",
    "DIAG_UNAVAILABLE": "❌ [Comms]: Static on the channel. Tensor unavailable.",
    "GENE_VITALITY_HEADER": "\n🧬 [Midichlorian Count Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Vitality: {score:.4f}",

    # Thermal & Physics Updates (Missing Strings Added)
    "THERMAL_SPIKE": "🔥 [R2-D2]: Beep-bloop! Overheating ({temp}°C). Diverting power to shields!",
    "THERMAL_RESUME": "❄️ [Hoth]: Temperature stabilized ({temp}°C). Engines re-engaged.",
    "CLEANUP_START": "\n🧹 [Garbage Chute]: One thing for sure, we're all gonna be a lot thinner...",
    "CLEANUP_END": "✅ [Docking Bay]: Cleanup complete. Ship is secured.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🌌 [Galaxy]: Preparing {symbol} for lightspeed...",
    "SPACE_BOUNDARY": "🌌 [Edge]: Outer Rim detected at {date}. Beyond is only the Unknown Regions.",
    "DATA_AUDIT_TARGET": "📊 [Intelligence]: Target Intel: {target}",
    "DATA_AUDIT_BARS": "📊 [Intelligence]: Total Datacrons: {count}",
    "DATA_AUDIT_SIGS": "📊 [Intelligence]: Rebel signals found: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [Empire]: Intelligence on '{target}' is missing from the archives!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Maintenance]: Purged {count} scrap-metal string dimensions.",
    "SPACE_DISCOVERY": "✅ [Exploration]: Charted {count} hyperlanes for navigation.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [Carbonite]: Frozen in perfection. Champion (F1={f1:.4f}) locked in Slot 1",
    "CORE_FIX_INDIVIDUAL": "🔧 [Pit Stop]: Calibrating moisture vaporators for program {i}",
    "CORE_CHAMP_LOST": "  ⚠️ [Trench Run]: We've lost R2! Restoring from memory bank to position 1",
    "PULSAR_NEW_RECORD": "🔥 [Holocron]: New High-Water Mark: {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Archives]: Saving blueprint (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🛑 [Admiral Ackbar]: It's a trap! Save aborted. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Droid]: R2 says the motivator is blown: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Medal]: Winner Ejected to the Archives. Features: {features} | F1: {f1:.4f} | Precision: {prec:.4f}",
    "PULSAR_CHUNK_LOG": "Sector {chunk} | MaxProb: {max_p:.3f} | Targets: {targets:.0f} | Fired: {fired:.0f} | F1: {f1:.4f}",
    
    # Hale-Bopp & Advanced Normalization
    "HALEBOPP_EJECT": "☄️ [Smuggler]: Kessel run complete. Delivering payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [Labs]: Extracted {count} midichlorian-rich dimensions.",
    "COSMIC_NORMALIZATION": "🔭 [Alliance]: Calibrating the navigation computer and galactic kinematics...",

    # Audit & Error States
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Briefing]: Sector Integrity Report",
    "ATMOSPHERIC_WASTE": "🚫 [Asteroids]: {count} dimensions destroyed (Scrap/Strings)",
    "NOSTRING_POLLUTION": "✅ [Shields]: No space-junk detected in the feature set.",
    "MATTER_CHECK_SUCCESS": "💎 [Solid]: All {count} dimensions are as solid as a thermal detonator.",
    "VOID_REPORT_WARNING": "⚠️ [Sarlacc]: {count} dimensions contain gaping holes (NaNs)",
    "DATA_DENSITY_CRITICAL": "🚨 [Death Star]: {count} columns are more than 50% empty! Abandon ship!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [Yoda]: No matter, there is. Ignite the universe, you must.",
    "INITIALIZATION_FAILURE": "❌ [Error]: The hyperdrive is leaking: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Attack Run {gen} Summary] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Targets {sigs} | Density {density:.4%}"
}