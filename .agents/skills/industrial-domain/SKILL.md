---
name: industrial-domain
description: >
  Industrial manufacturing domain knowledge for UNS platform. Triggers on tasks
  involving ISA-95/88 standards, production context (Lot/Step/Recipe), batch
  processing, SPC calculations (Cpk, X-bar/R), OEE calculations, equipment
  state model (SEMI E10), or pharma/F&B specific requirements.
---

# Industrial Domain Knowledge

## ISA-95 Hierarchy

Enterprise → Site → Area → Line → Equipment
- Maps directly to UNS Namespace Tree
- Each level has specific data ownership patterns

## Production Context

- `production_run` links IoT data to manufacturing context
- Fields: lot_id, product_id, recipe_id, step_id, equipment, start/end time
- Created by: MES CDC, gRPC WriteEvent, or **manual UI input** (for sites without MES)

## Equipment State Model (SEMI E10)

6 states: Productive, Standby, Engineering, Scheduled Down, Unscheduled Down, Non-Scheduled
- Raw vendor states map to E10 standard states
- State transitions stored in `ts_status`
- Used for OEE Availability calculation

## SPC (Statistical Process Control)

- Cpk = min((USL - μ) / 3σ, (μ - LSL) / 3σ)
- X-bar/R charts for process monitoring
- OOS (Out of Spec) detection triggers events
- Data source: `ts_measurements` with spec limits from product definition

## OEE (Overall Equipment Effectiveness)

- OEE = Availability × Performance × Quality
- Availability = (Planned - Downtime) / Planned
- Performance = (Ideal Cycle × Output) / Running Time
- Quality = Good Units / Total Units

## Command Flow

- Commands (MES → EAP) go through **direct channels** (OPC UA, REST), NOT through UNS
- UNS is the **observer/recorder**, not the command channel
- EAP publishes events (ProcessStarted, etc.) to UNS after completing operations

## Target Industries

- 🥇 Pharma CDMO + Fine Chemical (batch processing, FDA compliance)
- 🥈 F&B + EMS/SMT (OEE improvement, quality traceability)

## Reference

- System Spec: `docs/platform_system_spec.md` §1.4-1.7, §12, §13
- Architecture decisions: `docs/uns_architecture_decisions.md`
