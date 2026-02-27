"""
===============================================================================
 File:        freddy.py
 Theme:       A Nightmare on Elm Street
 Description: Slasher-horror themed strings. Sleep is the enemy.
===============================================================================
"""

STRING_TABLE = {
    # System & Data Ingestion
    "SPACE_IGNITE": "💤 [Dream]: Dragging {universe} into the boiler room for {symbol}... {start} -> {end}",
    "SPACE_BIG_BANG": "🔪 [Freddy]: You're all my children now! {dims} dimensions sliced and normalized.",
    "SPACE_THERMAL_HOT": "🔥 [Boiler]: It's getting hot in here ({temp}°C). The steam is rising...",
    "SPACE_THERMAL_COLD": "🧤 [Dream]: The furnace cooled down ({temp}°C). Back to the shadows.",
    "COMET_ORBIT": "🏃 [Victim]: Running from '{name}'. It's a long way to the end of the hall: {size}",
    "COMET_DISSIPATE": "💀 [Grave]: Program '{name}' didn't wake up in time.",
    "COMET_EJECTION_ERROR": "🩸 [Slash]: Can't escape the dream, {name}! Error: {e}",
    
    # Model & Singularity Init
    "SINGULARITY_INIT": "🧤 [Nightmare]: The glove is on {device}. Don't. Fall. Asleep.",
    "SINGULARITY_LENS": "👁️ [Hypnocil]: Looking through the fog. {lens} protocol engaged.",
    "SPACE_MATERIALIZING": "🏚️ [1428]: Rezzing {name} for {symbol}. Sweet dreams...",
    "COSMIC_NORMALIZATION": "🌀 [Surgery]: Peeling back the skin. Z-space prep starting.",
    "REDSHIFT_NORMALIZE": "🌀 [Distortion]: The walls are stretching. Z-Score normalization applied.",
    "GRAVITATIONALLENS_INIT": "👁️ [DreamState]: Seeing into your mind. GravitationalLens finding the fear.",
    "STANDARDEYE_INIT": "👁️ [Wide Awake]: I can see you! StandardEye engaged.",
    
    # Flight & Evolution (The Training Loop)
    "FLIGHT_WARP_INIT": "🧤 [Freddy]: Why are you screaming? I haven't even caught you yet!",
    "FLIGHT_GEN_START": "🧤 [Nightmare]: Round {gen}/{total}. Ready for a little tickle?",
    "FLIGHT_GEN_SUMMARY": "\n📊 [Scream Report - Night {gen}] ({duration:.1f}s)",
    "FLIGHT_METRIC_F1": "   TERROR_LEVEL: Avg {avg_f1:.4f} | Peak {max_f1:.4f}",
    "FLIGHT_METRIC_PREC": "   BLOOD_DEBT:   Avg {avg_prec:.4f} | Peak {max_prec:.4f}",
    "FLIGHT_METRIC_ACT": "   LUCIDITY:     Signals {sigs} | Density {density:.4%}",
    "FLIGHT_METRIC_WINNER": "   PRIME_VICTIM_SIGS: {sigs}",
    "FLIGHT_ALPHA_PEAK": "🏆 [Record]: A new masterpiece of pain! {f1:.4f} slices better than {old_f1:.4f}",
    "FLIGHT_STAGNATION": "📉 [Boredom]: You're not screaming loud enough. Counting sheep: {count}/{limit}",
    "FLIGHT_BEST_RECORD": "           Current Alpha Nightmare: {f1:.4f} (Night {gen})",
    "FLIGHT_REJECTED": "⚠️ [Burnt]: F1 {f1:.4f} rejected. Victim density ({sigs}) too quiet for the boiler ({min})",
    "FLIGHT_STAG_COUNT": "📉 [Boredom]: No progress: {count}/{limit}",
    "FLIGHT_EXTINCTION": "💀 [Wake Up]: WAKE UP! Everything is gone. Resetting the dream...",
    "FLIGHT_RAD_DEEP": "☢️  [Hell]: Dragging you deeper! Mutation spiked to 60%...",
    "FLIGHT_RAD_INJECT": "☢️  [Serum]: Injecting nightmare fuel into 40% of the population...",
    "FLIGHT_COMPLETE": "\n🏁 [Morning]: The sun is up. For now.",
    "FLIGHT_BEST_RESULT": "🥇 [Legend]: Night {gen} achieved F1 {f1:.4f}. This is your nightmare!",
    
    # Diagnostics & Audit
    "DIAG_SIGNALS": "🔍 [Evidence]: Claw marks found at: {locs}{suffix}",
    "DIAG_EMPTY": "   🔍 [Silence]: No one heard a thing (0 signals).",
    "DIAG_UNAVAILABLE": "❌ [Static]: The TV is just static. Tensor unavailable.",
    "GENE_VITALITY_HEADER": "\n🧬 [Deadly Indicators Top 10]:",
    "GENE_VITALITY_ROW": "   {rank}. {name:<20} | Vitality: {score:.4f}",

    # Thermal & Physics (Missing Strings Added)
    "THERMAL_SPIKE": "🔥 [Boiler]: It's getting hot in here ({temp}°C). The steam is rising...",
    "THERMAL_RESUME": "🧤 [Dream]: The furnace cooled down ({temp}°C). Back to the shadows.",
    "CLEANUP_START": "\n🧹 [Janitor]: Sweeping up the remains. No witnesses...",
    "CLEANUP_END": "✅ [Stable]: The dream is quiet. For now.",
    
    # Space & Matter Checks
    "SPACE_IGNITE_START": "🏚️ [1428]: Preparing {symbol} for the long sleep...",
    "SPACE_BOUNDARY": "🚧 [Dead End]: You hit the wall at {date}. There's no way out!",
    "DATA_AUDIT_TARGET": "📊 [Audit]: Terror Protocol: {target}",
    "DATA_AUDIT_BARS": "📊 [Audit]: Sleep Cycles: {count}",
    "DATA_AUDIT_SIGS": "📊 [Audit]: Screams recorded: {sigs}",
    "SPACE_ERROR_TARGET": "⚠️ [Missing]: I can't find '{target}' in your head!",
    "SPACE_CLEANUP_STRINGS": "🧹 [Trash]: Threw away {count} string-polluted memories.",
    "SPACE_DISCOVERY": "✅ [Hunt]: Found {count} ways to catch you.",
    
    # Evolution Core Logic
    "CORE_QUANTUM_LOCK": "💎 [Stitched]: You're mine now. Champion (F1={f1:.4f}) sewn into Slot 1",
    "CORE_FIX_INDIVIDUAL": "🔧 [Patch]: Sewing individual {i} back together.",
    "CORE_CHAMP_LOST": "  ⚠️ [Missing]: The Alpha escaped the dream! Dragging them back to position 1",
    "PULSAR_NEW_RECORD": "🔥 [Scream]: A new record of terror! {reason}",
    "PULSAR_SAVE_PENDING": "📍 [Trophy]: Pinning nightmare to the wall (F1={f1:.4f}, Prec={prec:.4f})...",
    "PULSAR_SAVE_ABORT": "🛑 [Interrupted]: Someone woke up. Save aborted. {reason}",
    "PULSAR_PHYSICS_FAIL": "⚠️ [Burned]: The data is scorched: {error}",
    "PULSAR_WINNER_EJECT": "🥇 [Eject]: Nightmare exported. Features: {features} | F1: {f1:.4f} | Precision: {prec:.4f}",
    "PULSAR_CHUNK_LOG": "Cycle {chunk} | Horror: {max_p:.3f} | Victims: {targets:.0f} | Fired: {fired:.0f} | F1: {f1:.4f}",
    
    # Hale-Bopp & Advanced Normalization
    "HALEBOPP_EJECT": "🚁 [Escape]: LZ reached? No, it's just another dream. Payload to 'checkpoints/{filename}'",
    "HALEBOPP_DUMPGENES": "🔬 [Autopsy]: Extracted {count} razor-sharp dimensions.",
    "COSMIC_NORMALIZATION": "🔭 [Autopsy]: Peeling back the layers of dream-state kinematics...",

    # Audit & Error States
    "DIMENSIONAUDIT_REPORT": "\n🔬 [Autopsy]: Sector Integrity Report",
    "ATMOSPHERIC_WASTE": "🚫 [Gutter]: {count} dimensions slaughtered (Non-numeric/Noise).",
    "NOSTRING_POLLUTION": "✅ [Pure]: The blood is clean. No string pollution detected.",
    "MATTER_CHECK_SUCCESS": "💎 [Solid]: All {count} dimensions are sharp as a blade (0 NaNs).",
    "VOID_REPORT_WARNING": "⚠️ [Holes]: {count} dimensions are missing pieces (NaNs)",
    "DATA_DENSITY_CRITICAL": "🚨 [Dying]: {count} columns are bleeding out! Data loss > 50%!",
    "UNINITIALIZED_RESOURCE_ERROR": "❌ [Sleepy]: You're not dreaming yet. Ignite the universe first.",
    "INITIALIZATION_FAILURE": "❌ [Glitch]: The nightmare stalled: {e}",
    "GENERATION_SUMMARY_HEADER": "\n📊 [Night {gen} Summary] ({duration:.1f}s)",
    "METRIC_F1_BLOCK": "   F1:          Avg {avg_f1:.4f} | Max {max_f1:.4f}",
    "METRIC_PRECISION_BLOCK": "   PRECISION:   Avg {avg_prec:.4f} | Max {max_prec:.4f}",
    "METRIC_ACTIVITY_BLOCK": "   ACTIVITY:    Screams {sigs} | Ratio {density:.4%}"
}