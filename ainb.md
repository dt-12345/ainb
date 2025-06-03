# AINB Crash Course

**AINB** (**AI** **N**ode **B**inary) is a file format that stores node graphs used to drive game logic and AI functionalities. In *Tears of the Kingdom*, there exist three categories of AINB files: **AI**, **Logic**, and **Sequence**. It is important to keep in mind which category of file you are currently working with (details will be discusses later). With the exception of logic files, AINB files are organized into **Commands** which the game can call upon to run the corresponding **Nodes**.

## Commands

Commands serve as the entrypoints into AINB files (except for logic files which will be discussed later) and have a single **Root Node**.

## Nodes

Nodes are the core of AINB files and are responsible for the logic and control flow of the file. Nodes are stored in an array and referenced by their index in said array. An invalid node index can be represented by 0x7fff (32767). Each node has both a name and a node category. The game uses these two identifiers to create the correct node object at runtime. The node category is an invisible property of a node that is only accessible from within the game's executable. Without checking the executable, the best way to know if a node is usable in a given file category is to see if it's used any vanilla files of that category. Tools such as `Starlight` can also help provide this information as well.

Here is a table of the valid node categories for each file category:

| File Category     | Node Categories                                   |
|-------------------|---------------------------------------------------|
| AI                | `AI`, `CommonAI`, `CommonNode`                    |
| Logic             | `Logic`, `CommonLogic`, `CommonNode`              |
| Sequence          | `AI`, `Sequence`, `CommonSequence`, `CommonNode`  |

The only exception to this rule is any node that begins with `Element_` as these are built-in node types that can be used in any file.

The reason only certain node categories can be used in certain file categories is that each file category corresponds to a specific AI controller associated with a specific class. For AI files, the controller is associated with the corresponding actor, for logic files, the controller is associated with the corresponding AI group, and for sequence files, the controller is associated with the corresponding scene. As a result, the information accessible to a node is dependent on its controller leading to some nodes being incompatible with certain file categories.

There is no way to know the exact behavior of each node with reverse engineering that node's function in the game's executable. However, oftentimes, it is possible to somewhat accurately guess what a node does from its name.

### Properties

**Properties** are internal parameters belonging to a node that can change the way it behaves. Properties are specific to each node type.

### Plugs/Links

**Plugs** are connections or links between two nodes. The name likely comes from visual node editors where you can "plug" one node into another. Plugs are used to pass data between nodes as well as to direct control flow. When used to direct control flow, the next node is referred to as the **Child Node**.

### Inputs/Outputs

Nodes can have both **Input** and **Output** parameters. Node inputs have a default value but can optionally be supplied from another node via a plug. Likewise, node outputs can be passed to another node via a plug as well. A node's inputs/outputs are specific to that node type.

### Queries

As previously stated, nodes can receive inputs via plugs from other nodes. The node whose output is supplied to another node is referred to as a **Query** as the receiving node is querying some data from that node. All query nodes are stored in an array and are referenced by their index in the query array.

### Expressions

The values of node parameters can be altered by **Expressions** which function as simple math/logic expressions that can do simple operations on a value. At the moment, there is no agreed upon way of editing or even representing these expressions. Each expression can optionally have a setup expression that is run once on node entry.

### Blackboard

Node parameters can also draw from an actor/AI group/scene's **Blackboard**. A blackboard is a means of local/scoped parameter/flag storage that can be shared.

### Attachments

**Attachments** are an addition that can be "attached" to a node to add additional functionality (note that attachment is not an official name). Attachments, like nodes, can also have properties.

### XLink Actions

Nodes can trigger a change in an actor's current **XLink action** when run. This is specified by the **Action Slot** to target and the **Action** to set that slot to.

### Modules

**Modules** are a means of triggering a separate AINB file as a node from one file. This allows you to combine nodes together to create custom behavior and then call upon this sequence of nodes similar to a function in many programming languages. Modules can have inputs and outputs similar to normal nodes. Additionally, they can have child nodes whose execution can be controlled from within the module.

## File Execution

Whenever a node is run, the game first runs all of its queries to update any data that the node may have queried. When a command is called from within the game's executable, the root node is run. Each node has three calculation functions: **Enter**, **Update**, and **Leave**. When a command is first called, the root node's enter calculation occurs. Following this, the root node's update calculation is run every frame until the current command changes or the actor/AI group/scene is unloaded when the root node's leave calculation is run.

### Logic Files

Logic files do not follow the standard execution procedure as they do not contain any commands. Without delving too much into the details, every node in a logic file is run independently every frame. This execution still follows the same enter, update, leave pattern with enter being run when the AI group is first created, leave being run when the AI group is destroyed, and update being run every frame in between. Note that any module nodes in logic files that are called from other logic files must have an entry in `Logic/NodeDefinition/Node.Product.120.aidefn.byml.zs` with the `PrefabModule` tag.

### Events

Actions and queries from events are carried out by the corresponding event member's event AI file. Each action/query in an event corresponds to a command in said AI file with the same name. The action/query's inputs are passed to the command's root node which also shares the same name. The root node then passes these event inputs as outputs to other nodes to carry out the requested action/query. The root node of an event command has a single plug named `Execute` which links to the logic for that action/query. Additionally, for queries, the result of the query is set by the AI file with the `ExecuteEventSetQueryValue` node. As these event actions/queries just correspond to an AI command, it is possible to create custom actions/queries by following this same pattern. The only additional requirement is that the command's root node have an entry in `AI/NodeDefinition/Node.Product.120.aidefn.byml.zs` with the `EventNode` tag (you can also optionally add the `EventTrigger` tag which changes how the corresponding command is processed). Without going into too much detail on event processing, `EventTrigger` causes the event command to be processed in a single frame, meaning that the node's enter, update, and leave are all ran immediately after one another. This only affects event actions, as standard actions are run across the span of several frames, until they return either a success or failure result.

## Node Types

### Built-in Nodes

#### Element_S32Selector, Element_F32Selector, Element_StringSelector, Element_RandomSelector, Element_BoolSelector

These nodes are selectors which conditionally select a child node based upon an input value and a condition corresponding to each child node. These are useful for control flow.

#### Element_Sequential

This node runs all connected child nodes sequentially. The next child node is only run when the previous one has finished (i.e. it has either a `Success` or `Failure` result) - because of this, be wary of using `Element_Sequential` with certain nodes (such as some `Execute` nodes) which may not terminate until the command itself is terminated.

#### Element_Simultaneous

This node runs all connected child nodes simultaneously. Unlike `Element_Sequential`, this `Element_Simultaneous` does not wait for the previous node to finish to run the next child node.

#### Element_Fork, Element_Join

These nodes are unused in *Tears of the Kingdom* but are still functional. `Element_Fork` splits execution into multiple separate branches while `Element_Join` will join execution back together. `Element_Join` has a `InFlowNum` property which specifies the number of `Element_Join` nodes that must be reached before execution is rejoined into a single branch. Execution then jumps to the next update node.

#### Element_Alert

This node is a stubbed, non-functional debugging node.

#### Element_Expression

This node allows for the custom processing of inputs via expressions. Inputs are processed in an expression and outputs are also set by the same expression.

#### Element_ModuleIF_Input_* and Element_ModuleIF_Output_*

These nodes are used to allow modules to receive inputs from and pass outputs to the calling AINB file. 

#### Element_ModuleIF_Child

These nodes are used by modules to access the child nodes of the module node and selectively choose one for execution.

#### Element_StateEnd

These nodes are used primarily in module sequence files to mark the end of the current command. They have a `TransitionCommand` property that specifies the name of the update link child node to continue execution on in the calling AINB file.

#### Element_SplitTiming

These nodes have three plugs named `Enter`, `Update`, and `Leave` which are run during the node's enter, update, and leave calculations. This allows for the control of when child nodes are calculated.

#### User-Defined Nodes

These are custom nodes specific to the game. In *Tears of the Kingdom*, these generally come in a few general types: `Execute`, `OneShot`, `Query`, `Selector`, `Hold`, and `Trigger` (sequence versions of AI nodes are generally prefixed with `Seq`). Of course, nodes outside of these groupings do exist and even within these groupings and the behavior of nodes is not 100% consistent.

`Execute` (AI/Sequence)
- `Execute` nodes generally run continuously for a command's duration - enter often involves setting up the node, update often is the main calculation of the node, and leave often cleans up anything that may need to be taken care of before the node is destroyed

`OneShot` (AI/Sequence)
- `OneShot` nodes generally run a single time at enter and then do nothing afterwards - however, many `OneShot` nodes have a `ExecuteEveryFrame` property which makes them run every update as well

`Query` (AI/Sequence)
- `Query` nodes generally are run every enter and update and act as queries, providing data to other nodes

`Selector` (AI/Sequence)
- `Selector` nodes generally direct control flow by selecting a child node for execution depending on some condition

`Hold` (Logic)
- `Hold` nodes are similar to `Execute` nodes except that they are for logic files - they usually receive some input via a plug and operate on said input continuously

`Trigger` (Logic)
- `Trigger` nodes generally have an input named `IsDrive` which determines whether or not to trigger the node - these nodes are run once on enter and once again each time `IsDrive` is true

A common naming scheme for nodes in *Tears of the Kingdom* is `<Type><System><Description>` where type is one of the above types, system is the relevant in-game system (such as physics, actor, sound, etc.), and description is a brief description of the node's function. Note that certain nodes may only function for certain actors. For example, `ExecutePlayer*` nodes will only work if used in Link's AI as they are dependent on accessing properties specific to Link.

#### ActorLogic (Logic only)

`ActorLogic` nodes are special nodes that correspond to an actor in an AI group (specified by the `InstanceName` property). These nodes must have an entry in `Logic/NodeDefinition/Node.Product.120.aidefn.byml.zs` with the `ActorLogic` tag which specifies its inputs and outputs. The node itself has no function other than to receive inputs and provide outputs. Common inputs are `Logic_Create`, `Logic_Delete`, and `Logic_Respawn` which control the creation, deletion, and respawning of the actor/preactor. The outputs of an `ActorLogic` node are generally set from within the game's executable, but can also be set directly in an actor's AI file with `ExecuteLogicSet*` nodes.

#### Event Nodes

Event nodes are nodes used for event actions and queries. See the above explanation for more details.