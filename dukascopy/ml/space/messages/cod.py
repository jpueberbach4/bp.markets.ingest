"""
===============================================================================
File:         cod.py
Theme:        Call of Duty / Modern Warfare
Description:  Tactical, comms-heavy strings for high-stakes operations.
===============================================================================
"""

STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "🔫 [HQ]: Initializing Op:{universe} for Asset:{symbol}... {start} -> {end}",
    "SPACE_BIG_BANG": "🛰️ [Overlord]: Satellite link established. {dims} sectors mapped and normalized.",
    "SPACE_THERMAL_HOT": "🔥 [Comms]: Hardware is red-lining ({temp}°C). Cease fire and cool down!",
    "SPACE_THERMAL_COLD": "❄️ [Comms]: Temperatures stabilized ({temp}°C). Resume mission.",
    "COMET_ORBIT": "📡 [UAV]: Tracking High-Value Target '{name}'. Effective range: {size}",
    "COMET_DISSIPATE": "💀 [Overlord]: Target '{name}' has been KIA.",
    "COMET_EJECTION_ERROR": "🟥 [FLASH]: Extract failure for '{name}': {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🛡️ [Safehouse]: Tactical Core online on {device}. Ready for deployment.",
    "SINGULARITY_LENS": "🔭 [Optics]: Thermal scope adjusted. {lens} filter active.",
    "SPACE_MATERIALIZING": "🚁 [Infil]: Dropping {name} for {symbol} into the AO.",
    "COSMIC_NORMALIZATION": "🌀 [Logistics]: Standardizing loadouts. Z-space prep engaged.",
    "REDSHIFT_NORMALIZE": "🌀 [Ballistics]: Calculating bullet drop. Relative coordinate shift applied.",
    "GRAVITATIONALLENS_INIT": "👁️ [Intel]: Scanning through walls. GravitationalLens pinpointing hostiles.",
    "STANDARDEYE_INIT": "👁️ [A-COG]: Clear view on the objective. StandardEye engaged.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "🚀 [Bravo 6]: Going dark. Commencing training extraction...",
    "FLIGHT_GEN_START": "🚀 [Squad]: Starting Wave {gen}/{total}. Check your corners.",
    "FLIGHT_GEN_SUMMARY": "\n📊 [After Action Report - Wave {gen}] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   K/D_RATIO:   Avg {avg_f1:.4f} | Peak {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   ACCURACY:    Avg {avg_prec:.4f} | Peak {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   ENGAGEMENT:  Signals {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   SQUAD_LEADER_SIGS: {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Promotion]: New Personal Best! {f1:.4f} beats previous record {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Intel]: No visual on improvement. Holding position: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Champion Record: {f1:.4f} (Wave {gen})",
    "FLIGHT_REJECTED": "⚠️ [Command]: F1 {f1:.4f} rejected. Engagement density ({sigs}) below minimum requirements ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Intel]: No progress: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [AC-130]: DANGER CLOSE. Wipe the board. Stagnation limit hit. Resetting AO...",
    "FLIGHT_RAD_DEEP": "☢️  [Nuke]: Tactical Nuke incoming! Mutation levels spiked to 60%...",
    "FLIGHT_RAD_INJECT": "☢️  [Gas]: Deploying Nova-6 into 40% of the population...",
    "FLIGHT_COMPLETE": "\n🏁 [HQ]: Mission accomplished. RTB for debrief.",
    "FLIGHT_BEST_RESULT": "🥇 [MVP]: Wave {gen} achieved F1 {f1:.4f}. Drinks are on you.",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Drone]: Contacts confirmed at indices: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Drone]: AO is clear. No contacts found (0 signals).",
    "DIAG_UNAVAILABLE": "❌ [Comms]: We've lost the uplink. Tensor data unavailable.",
    "GENE_VITALITY_HEADER": "\n🧬 [High-Value Indicators Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Vitality: {score:.4f}",
    "CLEANUP_START": "\n🧹 [Sweep]: Cleaning up the AO. Leaving no trace...",
    "CLEANUP_END": "✅ [Sweep]: Perimeter secured. System stable.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🚁 [Infil]: Preparing asset {symbol} for deployment...",
    "SPACE_BOUNDARY": "🚧 [Boundary]: Reached the edge of the AO at {date}. Return to combat zone!",
    "DATA_AUDIT_TARGET": "📊 [Audit]: Objective Protocol: {target}",
    "DATA_AUDIT_BARS": "📊 [Audit]: Intel Clusters: {count}",
    "DATA_AUDIT_SIGS": "📊 [Audit]: Confirmed hostiles: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [HQ]: Objective '{target}' not found in the manifest!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Armor]: Scrapped {count} corrupted/non-numeric feature plates.",
    "SPACE_DISCOVERY": "✅ [Scout]: Confirmed {count} valid fire lanes.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [Loadout]: Lock and Load. Champion (F1={f1:.4f}) saved to Slot 1",
    "CORE_FIX_INDIVIDUAL": "🔧 [Armory]: Re-tooling individual {i} for better performance.",
    "CORE_CHAMP_LOST": "  ⚠️ [Comms]: SQUAD LEADER DOWN! Restoring from latest backup to position 1",
    "PULSAR_NEW_RECORD": "🔥 [Killstreak]: New Personal Best! {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Intel]: Archiving mission data (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🛑 [Command]: Negative, Ghost Rider. Save aborted. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Repair]: Armor is compromised: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Exfil]: Extraction successful. Features: {features} | F1: {f1:.4f}",
    "PULSAR_CHUNK_LOG": "Sector {chunk} | MaxProb: {max_p:.3f} | Targets: {targets:.0f} | Fired: {fired:.0f}",
    
    # Normalizer & Error States
    "HALEBOPP_EJECT": "🚁 [Extraction]: LZ reached. Delivering payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [Intel]: Recovered {count} high-value intelligence dimensions.",
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Briefing]: AO Integrity Report",
    "ATMOSPHERIC_WASTE": "🚫 [Waste]: {count} dimensions KIA (Non-numeric/Noise)",
    "NOSTRING_POLLUTION": "✅ [Clean]: Area is secure. No string pollution detected.",
    "MATTER_CHECK_SUCCESS": "💎 [Solid]: All {count} dimensions are combat-ready (0 NaNs).",
    "VOID_REPORT_WARNING": "⚠️ [Void]: {count} dimensions are missing in action (NaNs)",
    "DATA_DENSITY_CRITICAL": "🚨 [Critical]: {count} columns are compromised! Data loss > 50%!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [HQ]: We don't have the gear. Initialize the Op first.",
    "INITIALIZATION_FAILURE": "❌ [Error]: We've got a jam: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Wave {gen} Performance] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Confirmed {sigs} | Ratio {density:.4%}"
}