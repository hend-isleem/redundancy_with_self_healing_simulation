# 3-Node Fault Tolerance System

## Overview
This system demonstrates fault tolerance and self-healing with 3 nodes using MAPE-K architecture and Byzantine fault tolerance.

## Key Features
- **Majority Voting**: Uses majority of 2/3 nodes for consensus
- **Byzantine Fault Detection**: Detects and quarantines nodes with erratic behavior
- **Self-Healing**: Automatic node recovery and fault isolation
- **Fault Injection**: Configurable fault modes for testing

## Running the System

### Quick Start
```bash
# Start entire system with fault simulation
start_system.bat
```

### Manual Start
```bash
# 1. Start coordination layer
python coordinationlayer.py

# 2. Start nodes with different configurations
python launcher.py 1 normal 50      # Normal node
python launcher.py 2 normal 52      # Normal node (slight offset)
python launcher.py 3 byzantine 50   # Faulty node
```

### Fault Modes
- `normal`: Standard operation with small noise
- `byzantine`: Random erratic readings
- `drift`: Gradual drift from correct values
- `intermittent`: Occasional wrong readings

## Self-Healing Techniques

1. **Heartbeat Monitoring**: Detects node failures
2. **Statistical Outlier Detection**: Identifies Byzantine faults
3. **Quarantine System**: Isolates faulty nodes
4. **Majority-Based Consensus**: Maintains operation with majority
5. **Automatic Recovery**: Nodes can rejoin after healing

## Testing Scenarios
The system automatically tests:
- Normal 3-node operation
- Byzantine fault tolerance
- Node failure recovery
- Consensus under faults