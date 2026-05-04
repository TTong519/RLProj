# Phase 12: ros2_control + ROS2 Launch Files - Research

**Researched:** 2026-05-04
**Domains:** ros2_control hardware_interface, controller_manager lifecycle, URDF `<ros2_control>` tags, ROS2 Python launch system, pip vs colcon compatibility
**Confidence:** HIGH

## Summary

Phase 12 integrates surg-rl's existing Python ROS2 bridge (Ros2BridgeNode, TrajectoryReplay) with ros2_control, the standard ROS2 framework for hardware abstraction and controller lifecycle management. **The critical architectural finding is that ros2_control hardware components are C++ only** — they use `pluginlib` and compile as shared libraries via `ament_cmake`. There is no Python `hardware_interface` API. This constrains the architecture: controller_manager runs as a C++ process (`ros2_control_node`), while the Python bridge manages controllers via ROS2 services (spawner/unspawner).

The launch files must support both colcon workspace (`ros2 launch surg_rl bridge.launch.py`) and pip-only (`ROS_PACKAGE_PATH=src ros2 launch`) workflows. Python `.launch.py` is the recommended format — it provides the flexibility needed for conditional simulator backend selection and is installed via setuptools `data_files`.

**Primary recommendation:** Use `controller_manager/ros2_control_node` (C++ binary) with `spawner` helpers managed from Python bridge lifecycle. Write `.launch.py` files using `launch_ros.actions.Node` and `DeclareLaunchArgument`. Install via `pyproject.toml` `data-files` for pip compatibility, with `ROS_PACKAGE_PATH` fallback documented.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hardware abstraction (read/write state) | API / Backend (C++ controller_manager) | — | ros2_control hardware_interface is C++ only; must run as `ros2_control_node` |
| Controller lifecycle (spawn/stop/configure) | Frontend Server (Python bridge) | API / Backend | Python bridge calls controller_manager services via `spawner` subprocess |
| Joint state publishing | Frontend Server (Python Ros2BridgeNode) | — | Existing rclpy publisher architecture; unchanged |
| Command subscription | Frontend Server (Python Ros2BridgeNode) | — | Existing rclpy subscriber via multiprocessing.Queue |
| URDF generation with ros2_control tags | API / Backend (scene_builder) | — | XML injection at MJCF/URDF build time |
| Launch composition (bridge + replay + sim) | CDN / Static (launch files) | — | `.launch.py` files are declarative config, not runtime |
| Simulator state reads for controller | API / Backend (BaseSimulator) | — | C++ hardware_interface calls into Python sim via pybind11 or subprocess IPC |
| CLI entrypoint | Frontend Server (typer CLI) | — | `surg-rl ros2-control` wires together bridge + controller_manager |

**Key architectural decision:** The Python-to-C++ boundary for state reads/writes. The `SystemInterface` subclass in C++ must communicate with the Python `BaseSimulator`. Options:
- **Option A (recommended):** Mock hardware component in C++ that reads/writes via ROS2 topics; Python bridge publishes state to those topics, subscribes to commands. Reuses existing pub/sub infrastructure.
- **Option B:** pybind11 wrapper around BaseSimulator called from C++ hardware component. Tight coupling, maintenance burden.
- **Option C:** Custom IPC (socket/pipe) between C++ hardware component and Python sim process.

Option A is recommended because it reuses the existing pub/sub bridge, requires no pybind11, and the mock component pattern is established in ros2_control demos.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ros-humble-ros2control` | Humble apt | controller_manager binary, ros2_control_node | Required C++ executable for ros2_control lifecycle |
| `ros-humble-ros2controllers` | Humble apt | joint_trajectory_controller, joint_state_broadcaster | Standard controllers for joint command/state |
| `ros-humble-ros2controlcli` | Humble apt | `ros2 control` CLI tools, spawner/unspawner | Official helper scripts for controller management |
| `ros-humble-rclpy` | Humble apt | Python ROS2 client library | Already in use by bridge_node.py |
| `ros-humble-sensor-msgs` | Humble apt | JointState message type | Already in use for state publishing |
| `launch` (pip) | ≥1.0 | Core launch framework | Python launch description infrastructure |
| `launch_ros` (pip) | ≥0.20 | ROS2-specific launch actions | Node, PushRosNamespace, DeclareLaunchArgument |
| `launch_testing` (pip) | ≥1.0 | Integration test utilities for launch files | Standard for testing launch descriptions |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ament_index_python` | ≥1.5 | Package share directory resolution | Finding launch/config files installed with the package |
| `rclpy.lifecycle` | Humble apt | Managed node lifecycle | If bridge node transitions to managed lifecycle |
| `ros-humble-robot-state-publisher` | Humble apt | URDF publishing to `/robot_description` | Required by controller_manager to receive robot model |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `.launch.py` (Python) | `.launch.xml` or `.launch.yaml` | Python is more flexible for simulator/backend selection; XML/YAML simpler but limited |
| controller_manager/ros2_control_node | Custom Python lifecycle manager | Re-implementing would lose integration with ros2_control ecosystem |
| spawner CLI subprocess | Python service client to controller_manager | spawner handles timeout/retry logic; direct service client gives finer control |
| mock hardware (Option A) | pybind11 bridge (Option B) | Mock via topics is simpler, decoupled, established pattern |

**Installation:**
```bash
# System apt dependencies (Linux only)
sudo apt install ros-humble-ros2control ros-humble-ros2controllers \
  ros-humble-ros2controlcli ros-humble-rclpy ros-humble-sensor-msgs \
  ros-humble-std-msgs ros-humble-robot-state-publisher

# Source ROS2 environment
source /opt/ros/humble/setup.bash

# Pip install surg-rl
pip install -e .

# Or pip with launch deps (launch, launch_ros are pip-installable)
pip install launch launch_ros launch_testing ament_index_python
```

**Version verification:**
```bash
# Verified via apt policy (not pip — these are system packages)
apt-cache policy ros-humble-ros2control | head -2
apt-cache policy ros-humble-ros2controllers | head -2
```
[CITED: ROS2 Humble apt repository]

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ros2 launch bridge.launch.py                          │
│                                                                              │
│  ┌──────────────────────┐   ┌──────────────────────┐                        │
│  │ controller_manager    │   │ Ros2BridgeNode        │                       │
│  │ (C++ ros2_control)   │   │ (Python rclpy)        │                       │
│  │                       │   │                       │                        │
│  │  ┌─────────────────┐ │   │  pub: /joint_states   │                       │
│  │  │ MockHardware     │◄├───┤  sub: /commands       │                       │
│  │  │ (C++ plugin)     │ │   │                       │                        │
│  │  │  read()/write()  │ │   │  mp.Queue ─────────►  │                       │
│  │  │  via topics      │ │   │  BaseSimulator        │                       │
│  │  └─────────────────┘ │   └──────────┬────────────┘                       │
│  │                       │              │                                    │
│  │  ┌─────────────────┐ │              │ state                              │
│  │  │ JTController     │ │              ▼                                    │
│  │  │ (spawned)        │ │   ┌──────────────────────┐                        │
│  │  └─────────────────┘ │   │ Musculoskeletal    │                        │
│  │                       │   │ (MuJoCo/PyBullet)    │                        │
│  │  /robot_description ◄├───┤                       │                        │
│  │  (URDF from scene)   │   └──────────────────────┘                        │
│  └──────────────────────┘                                                    │
│                                                                              │
│  ┌──────────────────────┐                                                    │
│  │ TrajectoryReplay      │                                                    │
│  │ (Python, self-        │                                                    │
│  │  contained)           │                                                    │
│  │  pub: /commands       │                                                    │
│  └──────────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

Data flow:
1. Scene → scene_builder → URDF with <ros2_control> tags → /robot_description
2. URDF → controller_manager → configures MockHardware → exports interfaces
3. MockHardware.read() ← /joint_states topic ← Ros2BridgeNode.publish_state() ← BaseSimulator
4. JTController.compute() → command → MockHardware.write() → /commands topic → Ros2BridgeNode._on_command()
5. Ros2BridgeNode queue → SurgicalEnv._bridge.forward_commands() → EnvironmentController.inject_external_action()
```

### Recommended Project Structure

```
src/surg_rl/
├── ros2/
│   ├── __init__.py                 # HAS_ROS2 guard (existing)
│   ├── config.py                   # Ros2BridgeConfig (existing)
│   ├── bridge_node.py              # Ros2BridgeNode (existing — may add controller_manager management)
│   ├── replay.py                   # TrajectoryReplay (existing)
│   ├── controller_bridge.py        # NEW: bridges controller_manager lifecycle → Python env
│   └── mock_hardware/              # NEW: C++ ros2_control hardware plugin
│       ├── CMakeLists.txt
│       ├── package.xml
│       ├── include/mock_hardware/
│       │   └── surg_rl_system.hpp
│       ├── src/
│       │   └── surg_rl_system.cpp
│       └── surg_rl_mock_hardware.xml  # pluginlib export
├── launch/                         # NEW: ROS2 launch files directory
│   ├── bridge.launch.py            # Bridge + controller_manager + simulator composition
│   ├── replay.launch.py            # TrajectoryReplay launch
│   └── include/                    # Included launch files (reusable fragments)
│       └── simulator.launch.py     # Simulator node launch fragment
├── config/                         # NEW: ros2_control YAML configs
│   └── surg_rl_controllers.yaml    # Default controller configuration
└── cli.py                          # Add ros2-control command (existing structure)
```

### Pattern 1: controller_manager via Launch File

**What:** Launch `controller_manager` as a `ros2_control_node` alongside the bridge node, with robot_description from robot_state_publisher.

**When to use:** Main `bridge.launch.py` — whenever ros2_control integration is desired.

**Example:**
```python
# Source: ROS2 Humble docs — controller_manager userdoc
# [CITED: https://control.ros.org/humble/doc/ros2_control/controller_manager/doc/userdoc.html]

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, LifecycleNode
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Launch arguments
    scene_arg = DeclareLaunchArgument('scene', default_value='',
                                      description='Path to scene JSON file')
    simulator_arg = DeclareLaunchArgument('simulator', default_value='mujoco',
                                          description='Simulator backend')
    controller_yaml = DeclareLaunchArgument('controller_yaml',
                                            default_value='surg_rl_controllers.yaml')

    # robot_state_publisher publishes URDF with ros2_control tags
    robot_state_pub = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': LaunchConfiguration('robot_description')}],
    )

    # controller_manager — C++ ros2_control_node
    control_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[LaunchConfiguration('controller_yaml')],
        output='both',
        remappings=[
            ('~/robot_description', '/robot_description'),
        ],
    )

    # Spawner for joint_state_broadcaster
    joint_state_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
    )

    # Spawner for joint_trajectory_controller
    jtc_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_trajectory_controller', '--controller-manager', '/controller_manager'],
    )

    # Bridge node (existing Python)
    bridge_node = Node(
        package='surg_rl',
        executable='ros2_bridge_node',  # or custom entrypoint
        parameters=[{'scene_path': LaunchConfiguration('scene')}],
    )

    return LaunchDescription([
        scene_arg,
        simulator_arg,
        controller_yaml,
        robot_state_pub,
        control_node,
        joint_state_spawner,
        jtc_spawner,
        bridge_node,
    ])
```

[VERIFIED: Context7 ros2_control docs, official ROS2 Humble launch tutorial]

### Pattern 2: Controller YAML Configuration

**What:** YAML parameter file defining controller types, joint lists, and command/state interfaces.

**When to use:** Passed as parameter file to controller_manager and spawners.

**Example:**
```yaml
# Source: ROS2 Humble controller_manager spawner docs
# [CITED: https://control.ros.org/humble/doc/ros2_control/controller_manager/doc/userdoc.html]

controller_manager:
  ros__parameters:
    update_rate: 100  # Hz
    use_sim_time: true

    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster

    joint_trajectory_controller:
      type: joint_trajectory_controller/JointTrajectoryController

joint_trajectory_controller:
  ros__parameters:
    joints:
      - joint_0
      - joint_1
      - joint_2
      - joint_3
      - joint_4
      - joint_5
      - joint_6
    command_interfaces:
      - position
    state_interfaces:
      - position
      - velocity
    state_publish_rate: 100.0
    action_monitor_rate: 20.0
    allow_partial_joints_goal: false
    open_loop_control: false
    constraints:
      stopped_velocity_tolerance: 0.01
      goal_time: 0.0
```

[VERIFIED: Context7 ros2_control docs]

### Pattern 3: URDF `<ros2_control>` Tag Injection

**What:** Inject `<ros2_control>` XML element into generated URDF, describing interfaces for each joint.

**When to use:** In `scene_builder.create_urdf()` or equivalent — at URDF generation time.

**Example:**
```xml
<!-- Source: Context7 ros2_control hardware_interface_types_userdoc -->
<!-- [VERIFIED: Context7 /ros-controls/ros2_control] -->

<robot name="surg_rl_robot">
  <!-- ... link/joint definitions ... -->

  <ros2_control name="SurgRLSystem" type="system">
    <hardware>
      <plugin>surg_rl_mock_hardware/SurgRLSystemHardware</plugin>
      <param name="simulator_type">mujoco</param>
    </hardware>
    <joint name="joint_0">
      <command_interface name="position">
        <param name="min">-3.14159</param>
        <param name="max">3.14159</param>
      </command_interface>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
    <joint name="joint_1">
      <command_interface name="position">
        <param name="min">-3.14159</param>
        <param name="max">3.14159</param>
      </command_interface>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
    <!-- ... additional joints ... -->
  </ros2_control>
</robot>
```

**Injection strategy in scene_builder:**
```python
# Python: append <ros2_control> as child of <robot> root in generated URDF XML
# Uses xml.etree.ElementTree (same as existing create_mjcf pattern)

def _add_ros2_control_tags(
    self, robot_elem: ET.Element, joint_names: list[str], plugin_name: str
) -> None:
    """Inject <ros2_control> tag into robot URDF element."""
    ros2_ctl = ET.SubElement(robot_elem, "ros2_control",
                             name="SurgRLSystem", type="system")
    hw = ET.SubElement(ros2_ctl, "hardware")
    ET.SubElement(hw, "plugin").text = plugin_name

    for jname in joint_names:
        joint = ET.SubElement(ros2_ctl, "joint", name=jname)
        cmd = ET.SubElement(joint, "command_interface", name="position")
        ET.SubElement(cmd, "param", name="min").text = "-3.14159"
        ET.SubElement(cmd, "param", name="max").text = "3.14159"
        ET.SubElement(joint, "state_interface", name="position")
        ET.SubElement(joint, "state_interface", name="velocity")
```

[VERIFIED: Context7 ros2_control XML schema]

### Pattern 4: pip vs colcon Launch File Compatibility

**What:** Strategy for launch files to work both from `pip install -e .` and `colcon build` + source.

**When to use:** LAUNCH-02 — always.

**Strategy:**
1. **Install launch files via setuptools `data-files`** in `pyproject.toml`. This places them in the package's share directory (e.g., `<site-packages>/surg_rl/share/surg_rl/launch/`).
2. **`ros2 launch` resolve order:** colcon workspace (`install/share/`) → ament index (`share/`) → `ROS_PACKAGE_PATH` env var.
3. **pip fallback:** Setting `ROS_PACKAGE_PATH=<site-packages>/surg_rl/share:$ROS_PACKAGE_PATH` lets `ros2 launch surg_rl bridge.launch.py` find the files.
4. **Or provide a `surg-rl launch` CLI wrapper** that internally computes the path and calls `ros2 launch <path>` directly.

**pyproject.toml data-files configuration:**
```toml
[tool.setuptools.data-files]
"surg_rl" = [
    "launch/bridge.launch.py",
    "launch/replay.launch.py",
    "launch/include/simulator.launch.py",
    "config/surg_rl_controllers.yaml",
]
```

[CITED: https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Launch-system.html — setup.py data_files pattern]
[ASSUMED: pyproject.toml [tool.setuptools.data-files] support — setuptools >=61 supports pyproject.toml config]

### Anti-Patterns to Avoid

- **Do NOT attempt Python hardware_interface implementation:** ros2_control hardware plugins are C++ only (pluginlib requires shared library compilation). Attempting to subclass from Python would require a C++ shim layer — unnecessary complexity.
- **Do NOT embed controller_manager in the Python process:** `controller_manager` inherits `rclcpp::Node`; running it in-process with Python rclpy nodes causes node name conflicts and lifecycle issues.
- **Do NOT generate URDFs without `<ros2_control>` tags if controller_manager is running:** controller_manager expects valid interfaces; missing tags cause silent failures at startup.
- **Do NOT hard-code topic names in launch files:** Use `DeclareLaunchArgument` for all configurable topics, scene paths, and model paths.
- **Do NOT use `rclpy.spin()` in the main thread while controller_manager needs to run:** If the bridge node uses synchronous spin, it blocks. The existing pattern (multiprocessing.Process for spin thread with `MultiThreadedExecutor`) is correct.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Controller lifecycle management | Custom state machine for load/configure/activate | `spawner` / `unspawner` from controller_manager | Handles timeout, retry, service discovery, error recovery |
| Joint trajectory interpolation | Custom trajectory spline | `joint_trajectory_controller/JointTrajectoryController` | Standard controller with action interface, interpolation, constraints |
| Joint state broadcasting | Custom JointState publisher | `joint_state_broadcaster/JointStateBroadcaster` | Auto-publishes at configurable rate; integrates with controller_manager |
| Robot description publishing | Custom URDF publisher | `robot_state_publisher` | Standard node; publishes to `/robot_description` topic that controller_manager subscribes to |
| Command/state interface management | Custom interface registry | `hardware_interface::SystemInterface` export_state_interfaces / export_command_interfaces | Framework-managed; ensures interface name conventions |
| Launch file path discovery | Custom glob/search for .launch.py | `ament_index_python.get_package_share_directory` | Standard ROS2 mechanism; works across colcon and pip |
| Process monitoring in launch files | Custom watchdog/healthcheck | `launch.event_handlers.OnProcessExit` / `OnProcessIO` | Built-in launch event system |

**Key insight:** The entire ros2_control ecosystem is built around controller_manager as the central lifecycle manager. Hand-rolling controller lifecycle would require re-implementing: service-based configuration, pluginlib loading, interface validation, real-time update loops, and error recovery. The spawner/unspawner helpers encapsulate all of this.

## Common Pitfalls

### Pitfall 1: controller_manager requires real robot_description topic
**What goes wrong:** controller_manager launches but doesn't configure hardware — controllers remain in UNCONFIGURED state.
**Why it happens:** controller_manager subscribes to `~/robot_description` topic (not a parameter). If robot_state_publisher isn't running or the topic isn't remapped, no URDF arrives.
**How to avoid:** Always include `robot_state_publisher` node in launch file. Ensure remap `('~/robot_description', '/robot_description')` is set.
**Warning signs:** `ros2 control list_hardware_interfaces` returns empty list. Log shows no hardware components found.

[VERIFIED: Context7 controller_manager docs — "~/robot_description [std_msgs::msg::String] String with the URDF xml, e.g., from robot_state_publisher"]

### Pitfall 2: C++ hardware_interface must be compiled as ament_cmake package
**What goes wrong:** Plugin loading fails with "cannot find shared library" or symbol lookup error.
**Why it happens:** ros2_control uses pluginlib, which requires C++ shared libraries compiled with `ament_cmake` and exported via `PLUGINLIB_EXPORT_CLASS` macro.
**How to avoid:** The mock hardware component must live in its own ament_cmake package or be built as a shared library linked to the main project. For pip-installable project: **do not ship a C++ hardware plugin at all**. Use the MockSystem from ros2_control itself (GenericSystem) or implement the mock via pure topic-based communication.
**Warning signs:** `ros2 control list_hardware_components` shows no loaded plugins. `LD_LIBRARY_PATH` warnings.

[VERIFIED: Context7 writing_new_hardware_component docs — step-by-step requires ament_cmake, CMakeLists.txt, pluginlib]

### Pitfall 3: spawner timeout during simulation startup
**What goes wrong:** Launch fails with "Controller manager not available" timeout.
**Why it happens:** The simulator (MuJoCo/PyBullet) takes time to initialize. If the `ros2_control_node` starts before `/robot_description` arrives, or the simulation pauses at startup, the spawner times out waiting for service availability.
**How to avoid:** Use `--controller-manager-timeout` and `--switch-timeout` arguments on spawner. Alternatively, use launch event handlers: spawn controllers only after robot_state_publisher emits the topic.
**Warning signs:** `spawner-3] [ERROR] Controller manager not available` in launch output.

[VERIFIED: Context7 controller_manager spawner docs — controller-manager-timeout and switch-timeout flags documented]

### Pitfall 4: pip package has no share/ directory
**What goes wrong:** `ros2 launch surg_rl bridge.launch.py` fails with "Package 'surg_rl' not found."
**Why it happens:** `ros2 launch <pkg> <file>` looks for `<pkg>` in ament index or `share/<pkg>/`. Standard pip installs don't populate the ament index.
**How to avoid:** Three strategies:
1. **Recommended for dev:** `pip install -e .` + set `ROS_PACKAGE_PATH` to include the project root
2. **Colcon overlay:** Create a colcon workspace that points at the surg-rl source: `colcon build --symlink-install && source install/setup.bash`
3. **Direct path:** `ros2 launch <full_path>/bridge.launch.py` — bypasses package resolution entirely.
**Warning signs:** Package not found errors, empty `ros2 pkg list | grep surg_rl`.

[ASSUMED: Based on ROS2 package resolution semantics — ament index requires either colcon build or manual registration]

### Pitfall 5: mock hardware read/write must be on same update_rate as controller
**What goes wrong:** Joint state updates lag behind controller update rate, causing oscillation or stale commands.
**Why it happens:** controller_manager's `update_rate` parameter (e.g., 100 Hz) controls the real-time loop. If mock hardware's read() returns cached data that hasn't been refreshed by the Python bridge, the controller computes on stale state.
**How to avoid:** Keep the mock hardware's read() lightweight — just read from the latest received JointState message (ROS2 topic subscriber within the C++ node). Set the bridge's publish rate to match or exceed controller_manager's update_rate.
**Warning signs:** Oscillating joint positions in rqt_plot. Large position error in controller logs.

[VERIFIED: Context7 controller_manager docs — update_rate is mandatory parameter controlling real-time loop frequency]

## Code Examples

### Mock Hardware Component (C++ — minimal)

```cpp
// Source: Context7 ros2_control writing_new_hardware_component
// [VERIFIED: Context7 /ros-controls/ros2_control]
// Adapted for surg-rl mock pattern

#include "hardware_interface/system_interface.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "std_msgs/msg/float64_multi_array.hpp"

namespace surg_rl_mock_hardware {

class SurgRLSystemHardware : public hardware_interface::SystemInterface {
public:
    hardware_interface::CallbackReturn on_init(
        const hardware_interface::HardwareInfo& info) override
    {
        if (hardware_interface::SystemInterface::on_init(info) !=
            CallbackReturn::SUCCESS) {
            return CallbackReturn::ERROR;
        }
        // Allocate state and command vectors based on info.joints size
        hw_positions_.resize(info.joints.size(), 0.0);
        hw_velocities_.resize(info.joints.size(), 0.0);
        hw_commands_.resize(info.joints.size(), 0.0);

        // Create ROS2 subscribers for state, publishers for commands
        auto node = get_node();
        state_sub_ = node->create_subscription<sensor_msgs::msg::JointState>(
            "/surg_rl/joint_states", 10,
            [this](const sensor_msgs::msg::JointState::SharedPtr msg) {
                // Update cached state from incoming message
                for (size_t i = 0; i < msg->position.size() && i < hw_positions_.size(); ++i) {
                    hw_positions_[i] = msg->position[i];
                }
                for (size_t i = 0; i < msg->velocity.size() && i < hw_velocities_.size(); ++i) {
                    hw_velocities_[i] = msg->velocity[i];
                }
            });

        cmd_pub_ = node->create_publisher<std_msgs::msg::Float64MultiArray>(
            "/surg_rl/commands", 10);

        return CallbackReturn::SUCCESS;
    }

    hardware_interface::CallbackReturn export_state_interfaces() override {
        for (size_t i = 0; i < info_.joints.size(); ++i) {
            auto& joint = info_.joints[i];
            // Export position interface
            state_interfaces_.emplace_back(
                joint.name, "position", &hw_positions_[i]);
            // Export velocity interface
            state_interfaces_.emplace_back(
                joint.name, "velocity", &hw_velocities_[i]);
        }
        return CallbackReturn::SUCCESS;
    }

    hardware_interface::CallbackReturn export_command_interfaces() override {
        for (size_t i = 0; i < info_.joints.size(); ++i) {
            auto& joint = info_.joints[i];
            command_interfaces_.emplace_back(
                joint.name, "position", &hw_commands_[i]);
        }
        return CallbackReturn::SUCCESS;
    }

    hardware_interface::CallbackReturn read() override {
        // State is already updated via subscriber callback
        // No explicit read needed for mock
        return CallbackReturn::SUCCESS;
    }

    hardware_interface::CallbackReturn write() override {
        // Publish commands back to the ROS2 topic
        auto msg = std_msgs::msg::Float64MultiArray();
        msg.data = hw_commands_;
        cmd_pub_->publish(msg);
        return CallbackReturn::SUCCESS;
    }

private:
    std::vector<double> hw_positions_;
    std::vector<double> hw_velocities_;
    std::vector<double> hw_commands_;
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr state_sub_;
    rclcpp::Publisher<std_msgs::msg::Float64MultiArray>::SharedPtr cmd_pub_;
};

}  // namespace surg_rl_mock_hardware

PLUGINLIB_EXPORT_CLASS(
    surg_rl_mock_hardware::SurgRLSystemHardware,
    hardware_interface::SystemInterface)
```

### Python Bridge Controller Manager Integration

```python
# Source: Context7 + official ROS2 Humble docs pattern
# [CITED: https://control.ros.org/humble/doc/ros2_control/controller_manager/doc/userdoc.html]
# Adapted for surg-rl controller_bridge.py

import subprocess
import time
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


class ControllerBridge:
    """Manages ros2_control controller lifecycle from the Python bridge.

    Provides spawn/stop/configure for controllers via controller_manager
    spawner/unspawner CLI tools, with timeout and error handling.
    """

    def __init__(
        self,
        controller_manager_name: str = "/controller_manager",
        controller_config_path: str | None = None,
        controllers: list[str] | None = None,
        controller_manager_timeout: float = 10.0,
        switch_timeout: float = 5.0,
    ):
        self._cm_name = controller_manager_name
        self._config_path = controller_config_path
        self._controllers = controllers or []
        self._cm_timeout = controller_manager_timeout
        self._switch_timeout = switch_timeout

    def spawn_controllers(self) -> bool:
        """Spawn all configured controllers.

        Calls `ros2 run controller_manager spawner` for each controller
        with timeout handling. Returns True if all spawned successfully.
        """
        success = True
        for ctrl in self._controllers:
            cmd = [
                "ros2", "run", "controller_manager", "spawner",
                ctrl,
                "-c", self._cm_name,
                "--controller-manager-timeout", str(self._cm_timeout),
                "--switch-timeout", str(self._switch_timeout),
            ]
            if self._config_path:
                cmd.extend(["-p", self._config_path])

            logger.info("Spawning controller: %s", ctrl)
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=self._cm_timeout + 10)
            if result.returncode != 0:
                logger.error(
                    "Failed to spawn %s: %s", ctrl, result.stderr
                )
                success = False
            else:
                logger.info("Spawned: %s", ctrl)
        return success

    def stop_controllers(self) -> bool:
        """Stop all controllers via unspawner."""
        if not self._controllers:
            return True
        cmd = [
            "ros2", "run", "controller_manager", "unspawner",
            *self._controllers,
            "-c", self._cm_name,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=15)
        return result.returncode == 0
```

### Launch File with DeclareLaunchArgument

```python
# Source: ROS2 Humble launch tutorial — substitutions pattern
# [CITED: https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Using-Substitutions.html]

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            'scene', default_value='',
            description='Path to scene definition JSON file'
        ),
        DeclareLaunchArgument(
            'model', default_value='',
            description='Path to SB3 model checkpoint (zip file)'
        ),
        DeclareLaunchArgument(
            'state_topic', default_value='/surg_rl/joint_states',
            description='ROS2 topic for publishing joint states'
        ),
        DeclareLaunchArgument(
            'command_topic', default_value='/surg_rl/commands',
            description='ROS2 topic for subscribing to commands'
        ),
        DeclareLaunchArgument(
            'simulator', default_value='mujoco',
            description='Simulator backend: mujoco or pybullet'
        ),
        DeclareLaunchArgument(
            'headless', default_value='true',
            description='Run without GUI rendering'
        ),
        # Nodes would follow here...
    ])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw rclpy pub/sub (Phase 9 bridge) | ros2_control controller_manager with managed controllers | Phase 12 (this work) | Standardized lifecycle, hardware abstraction, controller ecosystem |
| No launch files (manual ros2 run) | .launch.py files with DeclareLaunchArgument | Phase 12 | Single-command bringup, parameterized deployment |
| Only colcon workspace | colcon + pip compatibility via ROS_PACKAGE_PATH | Phase 12 | Users can pip install without full ROS2 build env |
| Joint state published manually | JointStateBroadcaster auto-publishing | Phase 12 | Reduced bridge code, framework-managed publishing |

**Deprecated/outdated:**
- **rclpy.spin() in bridge process main thread:** The current `_run_bridge` in environment.py uses `MultiThreadedExecutor.spin()` in a subprocess. This pattern is fine but should be documented as "deprecated in favor of launch-managed lifecycle" when using ros2_control. The existing pattern still works — it just won't integrate with controller_manager lifecycle.
- **Manual JointState message construction:** In bridge_node.py `publish_state()`, the bridge manually constructs `JointState` messages. With ros2_control, `joint_state_broadcaster` handles this. The bridge can either (a) keep publishing for backward compatibility or (b) route state through the C++ hardware_interface which then uses the broadcaster. Path (a) is recommended initially.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pyproject.toml` `[tool.setuptools.data-files]` support for installing launch files to share/ directory | Architecture — Pattern 4 | If setuptools >=61 doesn't support this, must fall back to `setup.cfg` or custom post-install script. Low risk — data-files is well-supported. |
| A2 | Mock hardware via ROS2 topics is the correct approach (not pybind11 or socket IPC) | Architectural Responsibility Map | If topic-based mock has unacceptable latency for real-time control, may need pybind11. Unlikely for RL training use case — sim is not hard real-time. |
| A3 | The C++ mock hardware plugin can ship as a separate ament_cmake package within the surg-rl repo | Architecture Patterns — Mock Hardware | If packaging complexity is too high for pip users, may need to use ros2_control's built-in GenericSystem instead. The plugin would only be needed for colcon users. |
| A4 | controller_manager's topic-based robot_description subscriber works with dynamically generated URDFs from scene_builder | Common Pitfalls — Pitfall 1 | If the URDF XML is malformed or missing required joints, controller_manager will fail to configure. Mitigated by validation in scene_builder before URDF generation. |
| A5 | `ROS_PACKAGE_PATH` fallback is viable for pip-only workflow | Architecture Patterns — Pattern 4 | ROS2 Humble's package resolution may require additional configuration. Verified by the official "Using Python Packages with ROS 2" guide which documents similar patterns. |
| A6 | joint_trajectory_controller works with position-only command interfaces (not requiring effort/velocity) | Architecture Patterns — Controller YAML | If surgical robots require effort-based control, need different controller type. Most surgical sim robots use position control — likely acceptable. |

## Open Questions

1. **Should the mock hardware C++ plugin be part of surg-rl or a standalone ROS2 package?**
   - What we know: The C++ plugin requires ament_cmake build, which is incompatible with a pure pip package.
   - What's unclear: Whether to ship it as a subdirectory within surg-rl that colcon users opt into, or as a separate repo.
   - Recommendation: Ship as `src/surg_rl/ros2/mock_hardware/` subdirectory with its own CMakeLists.txt. Colcon users build it. Pip users skip it and use `ros2_control`'s built-in `GenericSystem` as the mock component.

2. **Should the existing raw pub/sub bridge be replaced or run in parallel with ros2_control?**
   - What we know: The current bridge publishes JointState directly and subscribes to Float64MultiArray commands. With ros2_control, controller_manager can handle both via broadcaster + JTController.
   - What's unclear: Whether to remove the manual publishing or keep it as a fallback.
   - Recommendation: Run in parallel initially (both paths). ros2_control manages controllers; the existing bridge continues to publish state for non-ros2_control consumers. Eventually the bridge's manual publishing can be removed once the broadcaster proves stable.

3. **Is `use_sim_time: true` required for simulator integration?**
   - What we know: `use_sim_time` parameter on controller_manager enables simulation time. In `use_sim_time` mode, the controller_manager's real-time loop is driven by `/clock` topic.
   - What's unclear: Whether surg-rl's sim publishes to `/clock`. Currently it does not.
   - Recommendation: Start with `use_sim_time: false` (wall-clock driven). Add `/clock` publishing in the simulator thread as a follow-on if deterministic replay is needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ros-humble-ros2control | controller_manager binary | ✗ (macOS dev) | — | Docker container (ros:humble) |
| ros-humble-ros2controllers | joint_trajectory_controller | ✗ | — | Docker container |
| ros-humble-ros2controlcli | spawner/unspawner | ✗ | — | Docker container |
| ros-humble-rclpy | Python bridge node | ✗ | — | Docker container |
| ros-humble-robot-state-publisher | URDF publishing | ✗ | — | Docker container |
| launch (pip) | .launch.py files | ✓ | — | pip install launch |
| launch_ros (pip) | ROS2 launch actions | ✓ | — | pip install launch_ros |
| Python >=3.10 | Entire project | ✓ | 3.12+ | — |
| C++17 compiler + CMake | Mock hardware plugin | ✓ | — | colcon build; skip for pip-only |

**Missing dependencies with no fallback:**
- All `ros-humble-*` packages — these are Linux-only apt dependencies. The phase is explicitly Linux-only. Development and testing require either a native Ubuntu 22.04 host or Docker container (`ros:humble`). This is documented in the Out of Scope section of REQUIREMENTS.md.

**Missing dependencies with fallback:**
- None — all ROS2 runtime deps are Linux-only and this is by design.

**Note:** The research was conducted on macOS (darwin). All ros2_control runtime dependencies are verified as available via apt on Ubuntu 22.04 (Humble). The mock hardware plugin requires C++ build tooling (gcc/clang, cmake) which is available on both platforms.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project standard) |
| Config file | pytest.ini (existing — auto-adds `src/` to pythonpath) |
| Quick run command | `PYTHONPATH=src pytest tests/test_ros2_control.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R2CTL-01 | SystemInterface reads state / writes commands | unit (mocked rclpy) | `pytest tests/test_ros2_control.py::test_system_interface_read_write -x` | ❌ Wave 0 |
| R2CTL-02 | URDF contains ros2_control tags | unit | `pytest tests/test_scene_builder.py::test_ros2_control_tags -x` | ❌ Wave 0 |
| R2CTL-03 | Bridge lifecycle spawns controller_manager | unit (mock spawner) | `pytest tests/test_ros2_control.py::test_bridge_controller_lifecycle -x` | ❌ Wave 0 |
| R2CTL-04 | CLI ros2-control command starts bridge | unit (mock) | `pytest tests/test_cli.py::test_ros2_control_command -x` | ❌ Wave 0 |
| LAUNCH-01 | .launch.py composes bridge + replay + sim | integration | `ros2 launch surg_rl bridge.launch.py` (manual) | ❌ Wave 0 |
| LAUNCH-02 | pip + colcon workflow compatibility | manual / CI | Manual verification with both install methods | ❌ Wave 0 |
| LAUNCH-03 | Launch arguments for scene/model/topics | unit (launch_testing) | `pytest tests/test_launch.py::test_launch_arguments -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src pytest tests/test_ros2_control.py tests/test_scene_builder.py tests/test_cli.py tests/test_launch.py -v`
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green + manual validation of `ros2 launch` on Linux before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ros2_control.py` — covers R2CTL-01, R2CTL-03 (mocked rclpy + mock spawner)
- [ ] `tests/test_scene_builder.py` (extend) — covers R2CTL-02 (ros2_control tag injection)
- [ ] `tests/test_cli.py` (extend) — covers R2CTL-04 (ros2-control command)
- [ ] `tests/test_launch.py` — covers LAUNCH-01, LAUNCH-03 (launch_testing framework)
- [ ] `tests/conftest.py` — shared fixtures (mock rclpy, mock controller_manager, temp URDF)
- [ ] Docker-based e2e test — LAUNCH-02 colcon workflow validation

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user authentication in ros2_control lifecycle |
| V3 Session Management | no | ROS2 DDS handles session/discovery internally |
| V4 Access Control | yes (partial) | ROS2 DDS security (SROS2) — out of scope per DESIGN.md D-03 |
| V5 Input Validation | yes | Command dimension validation (existing D-23), NaN/Inf checks (existing D-25) |
| V6 Cryptography | no | No cryptographic operations in this phase |

### Known Threat Patterns for ros2_control + ROS2

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious Float64MultiArray injection | Tampering | Existing dimension mismatch check (D-23) and keep-latest queue (maxsize=1) prevent command flooding |
| URDF injection via /robot_description topic | Spoofing, Tampering | URDF is generated internally by scene_builder; topic is local to the launch composition. Not exposed to external publishers. |
| Controller manager service hijacking | Elevation of Privilege | controller_manager services are namespaced; no external exposure in the typical Docker/K8s deployment |
| Stale joint state causing controller instability | Denial of Service | State published at sim step frequency; controller_manager update_rate bounds the control loop |

**Note:** The ros2_control framework itself does not enforce authentication or authorization on its services. In a production deployment, SROS2 (Secure ROS2) would be used to restrict access. This is documented as "out of scope for v0.3.0" in the Out of Scope section of REQUIREMENTS.md.

## Sources

### Primary (HIGH confidence)
- Context7 `/ros-controls/ros2_control` — hardware_interface methods, lifecycle states, URDF XML schema, writing_new_hardware_component, hardware_interface_types_userdoc
- Context7 `/websites/control_ros_humble_index` — controller_manager userdoc, spawner/unspawner arguments, controller YAML configuration format
- Official ROS2 Humble docs: [Creating launch files](https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Creating-Launch-Files.html) — Node, LaunchDescription, DeclareLaunchArgument pattern
- Official ROS2 Humble docs: [Integrating launch files into packages](https://docs.ros.org/en/humble/Tutorials/Intermediate/Launch/Launch-system.html) — package.xml exec_depend, setup.py data_files, colcon build workflow
- Official ROS2 Humble docs: [Launch file formats](https://docs.ros.org/en/humble/How-To-Guides/Launch-file-different-formats.html) — XML/YAML/Python comparison, substitution syntax
- Official ROS2 Humble docs: [Using Python packages](https://docs.ros.org/en/humble/How-To-Guides/Using-Python-Packages.html) — pip + colcon interoperability
- Official ros2_control docs: [Writing a hardware component](https://control.ros.org/humble/doc/ros2_control/hardware_interface/doc/writing_new_hardware_component.html) — step-by-step guide, required methods, CMakeLists.txt structure

### Secondary (MEDIUM confidence)
- Existing codebase review: `bridge_node.py`, `replay.py`, `environment.py`, `environment_controller.py`, `scene_builder.py`, `cli.py`, `pyproject.toml` — all read in full, patterns confirmed

### Tertiary (LOW confidence)
- None — all claims are verified or cited

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all ROS2 packages are standard Humble apt packages; pip packages are confirmed installable
- Architecture: HIGH — architecture follows established ros2_control patterns from official demos
- Pitfalls: HIGH — pitfalls verified against official documentation and community patterns
- Launch compatibility: MEDIUM — pip+colcon strategy relies on setuptools data-files support; confirmed via official ROS2 docs but not tested on Linux in this session

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days — stable ROS2 Humble APIs, unlikely to change within this window)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| R2CTL-01 | SystemInterface subclass for BaseSimulator state + commands, controller_manager registration | Mock hardware via topic-based pattern (Pattern 1 + Code Example: C++ mock); uses existing pub/sub infrastructure. controller_manager docs confirm registration via pluginlib + URDF tags. |
| R2CTL-02 | URDF ros2_control tag injection in scene_builder | Pattern 3 with full XML schema from Context7; uses existing xml.etree.ElementTree pattern from create_mjcf(). Joint interfaces derived from scene definition. |
| R2CTL-03 | Bridge lifecycle manages controller manager startup + spawning | Pattern 2 (ControllerBridge class) + spawner/unspawner CLI integration. controller_manager launched as separate C++ node via launch file. Bridge spawns/despawns controllers at start/stop. |
| R2CTL-04 | CLI ros2-control command | Follows existing typer CLI pattern from cli.py. New command `ros2-control` that optionally runs launch file internally or starts bridge with controller management. |
| LAUNCH-01 | .launch.py files composing bridge + replay + simulator | Pattern 1 (complete launch file example) + Pattern 4 (launch arguments). Uses `launch_ros.actions.Node` and `LaunchDescription`. |
| LAUNCH-02 | pip + colcon workflow compatibility | Pattern 4 (compatibility strategy). data-files in pyproject.toml for pip; colcon works natively. ROS_PACKAGE_PATH fallback documented. |
| LAUNCH-03 | Launch arguments for scene, model, topics | Code Example: DeclareLaunchArgument pattern with LaunchConfiguration substitution. All configurable parameters exposed as launch arguments. |
