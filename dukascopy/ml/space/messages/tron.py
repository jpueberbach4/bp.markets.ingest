"""
===============================================================================
File:         tron.py
Theme:        The Grid / TRON Legacy
Description:  Neon-circuitry based string table for the digital frontier.
===============================================================================
"""
STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "🟦 [GRID]: Resolving {universe} sectors for User:{symbol}... {start} >> {end}",
    "SPACE_BIG_BANG": "⚡ [GRID]: System Expansion Successful. {dims} dimensions synchronized with the Master Control.",
    "SPACE_THERMAL_HOT": "🟧 [CORE]: Thermal surge detected ({temp}°C). Diverting power to heat sinks...",
    "SPACE_THERMAL_COLD": "🟦 [CORE]: Equilibrium restored ({temp}°C). Re-engaging primary light-cycles.",
    "COMET_ORBIT": "💠 [IO]: Establishing datastream for {name}. Buffer length: {size}",
    "COMET_DISSIPATE": "💠 [IO]: Program {name} has de-rezzed.",
    "COMET_EJECTION_ERROR": "🟥 [IO_ERROR]: Resolution failure in program {name}: {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🌀 [SINGULARITY]: Logic core instantiated on {device}",
    "SINGULARITY_LENS": "🥏 [LENS]: Aligning identity disc. {lens} protocols active.",
    "SPACE_MATERIALIZING": "🟦 [GRID]: Rezzing {name} for User:{symbol}...",
    "COSMIC_NORMALIZATION": "🌀 [GRID]: Applying Bitstream Normalization...",
    "REDSHIFT_NORMALIZE": "🌀 [GRID]: Shifting vectors. Relative coordinate normalization engaged.",
    "GRAVITATIONALLENS_INIT": "🥏 [LENS]: Piercing the digital void. GravitationalLens resolving hidden bits.",
    "STANDARDEYE_INIT": "🥏 [LENS]: Accessing User vision. StandardEye resolving hidden bits.",
    
    # Flight & Evolution Training
    "FLIGHT_WARP_INIT": "🏍️ [GAME_GRID]: Initiating high-speed evolutionary cycle...",
    "FLIGHT_GEN_START": "🏍️ [GAME_GRID]: Commencing Cycle {gen}/{total}",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Cycle {gen} Diagnostics] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   F1_SCORE:    Avg {avg_f1:.4f} | Peak {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   PRECISION:   Avg {avg_prec:.4f} | Peak {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   BIT_DENSITY: Total Sigs {sigs} | Ratio {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   CHAMP_SIGS:  {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [GAME_GRID]: New ISO discovered! {f1:.4f} out-performs {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [GAME_GRID]: Logic loop detected. Stagnation: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Champion Program: {f1:.4f} (Cycle {gen})",
    "FLIGHT_REJECTED": "🟥 [GAME_GRID]: Program F1 {f1:.4f} de-rezzed. Signal density ({sigs}) below safety threshold ({min})",
    "FLIGHT_STAG_COUNT": "📉 [GAME_GRID]: Stagnation: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [GAME_GRID]: SYSTEM PURGE. Logic failure. Resetting environment...",
    "FLIGHT_RAD_DEEP": "☢️  [GAME_GRID]: DEEP RE-PROGRAMMING. Intensifying bit-mutation (60%)...",
    "FLIGHT_RAD_INJECT": "☢️  [GAME_GRID]: Injecting noise-code into 40% of programs...",
    "FLIGHT_COMPLETE": "\n🏁 [GAME_GRID]: Grid execution finished.",
    "FLIGHT_BEST_RESULT": "🥇 [CHAMPION]: Cycle {gen} produced optimal code with F1 {f1:.4f}",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [DEBUG]: Program {idx} executed at addresses: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [DEBUG]: Program {idx} returned zero output.",
    "DIAG_UNAVAILABLE": "🟥 [DEBUG]: Bit-tensor unavailable. Check core dump.",
    "GENE_VITALITY_HEADER": "\n🧬 [High-Impact Logic Gates]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Vitality: {score:.4f}",
    "CLEANUP_START": "\n🟦 [SYSTEM]: De-fragmenting the Oort sectors...",
    "CLEANUP_END": "🟦 [SYSTEM]: De-fragmentation complete. System stable.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🟦 [GRID]: Igniting light-streams for {symbol}...",
    "SPACE_BOUNDARY": "🟦 [GRID]: System wall detected at {date}. Beyond is only the abyss.",
    "DATA_AUDIT_TARGET": "📊 [AUDIT]: Target Protocol: {target}",
    "DATA_AUDIT_BARS": "📊 [AUDIT]: Total Data Clusters: {count}",
    "DATA_AUDIT_SIGS": "📊 [AUDIT]: Positive Interrupts: {sigs}",
    "SPACE_ERROR_TARGET": "🟥 [GRID_ERROR]: Protocol '{target}' not found in bitstream!",
    "SPACE_CLEANUP_STRINGS": "🧹 [GRID]: Purged {count} string-corrupted data sectors.",
    "SPACE_DISCOVERY": "🟦 [GRID]: Verified {count} stable dimensions.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [SINGULARITY]: Quantum Lock: Champion (F1={f1:.4f}) preserved in static buffer 1",
    "CORE_FIX_INDIVIDUAL": "🔧 [SYSTEM]: Repairing bit-collision for individual {i}",
    "CORE_CHAMP_LOST": "  🟥 [SYSTEM]: Champion de-rezzed! Restoring from back-up to position 1",
    "PULSAR_NEW_RECORD": "⚡ [EVOLUTION]: New High-Water Mark: {reason}",
    "PULSAR_SAVE_PENDING": "📍 [SYSTEM]: Archiving candidate program (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🟥 [SYSTEM]: Archive aborted. {reason}",
    "PULSAR_PHYSICS_FAIL": "🟥 [SYSTEM]: Failed to serialize physics parameters: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [SYSTEM]: Winner Code Exported. Dimensions: {features} | F1: {f1:.4f}",
    "PULSAR_CHUNK_LOG": "Buffer {chunk} | MaxProb: {max_p:.3f} | Targets: {targets:.0f} | Fired: {fired:.0f}",
    
    # Normalizer & Error States
    "HALEBOPP_EJECT": "💠 [IO]: Target reached. Exporting program payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [IO]: Materialized {count} elite logic gates.",
    "DIMENSIONAUDIT_REPORT": "\n🔬 [AUDIT]: Dimension Integrity Report",
    "ATMOSPHERIC_WASTE": "🟥 [WASTE]: {count} sectors dropped (String-corruption/Non-numeric)",
    "NOSTRING_POLLUTION": "🟦 [GRID]: No code-leakage detected in requested features.",
    "MATTER_CHECK_SUCCESS": "💎 [GRID]: All {count} sectors are solid (0 Null-bits).",
    "VOID_REPORT_WARNING": "🟧 [GRID]: Null-bit leak identified in {count} sectors",
    "DATA_DENSITY_CRITICAL": "🟥 [CRITICAL]: {count} sectors have >50% data loss!",
    "UNINITIALIZED_RESOURCE_ERROR": "🟥 [GRID_ERROR]: No matter found. Resolve the Grid first.",
    "INITIALIZATION_FAILURE": "🟥 [SYSTEM_ERROR]: Runtime error during init: {e}",
    
    # Summaries
    "GENERATION_SUMMARY_HEADER": "\n📊 [Cycle {gen} Summary] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Total Sigs {sigs} | Density {density:.4%}"
}