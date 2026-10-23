from typing import Protocol

from langgraph.graph import END, START, StateGraph

from testpilot_wf.schemas import WorkflowState


class AgentProtocol(Protocol):
    name: str
    writes: set[str]

    def invoke(self, state: WorkflowState) -> dict: ...


class AgentRegistry:
    def __init__(self):
        self.agents: dict[str, AgentProtocol] = {}

    def register(self, agent: AgentProtocol, *, replace=False):
        if (
            not isinstance(agent.name, str)
            or not agent.name.strip()
            or agent.name in {"controller", START, END}
            or any(character in agent.name for character in (":", "|"))
        ):
            raise ValueError("Invalid/reserved agent name")
        if agent.name in self.agents and not replace:
            raise ValueError(f"Agent already registered: {agent.name}")
        self.agents[agent.name] = agent
        return self

    def get(self, name):
        return self.agents[name]


class WorkflowBuilder:
    """A controlled chain containing execution; retries restart the whole chain."""

    def __init__(self, registry, chain=("generation", "execution")):
        if not chain or chain[0] != "generation" or "execution" not in chain:
            raise ValueError("Chain must start generation and contain execution")
        if len(set(chain)) != len(chain):
            raise ValueError("Duplicate nodes are not allowed")
        for name in chain:
            if name in {"controller", START, END}:
                raise ValueError("Routing nodes cannot appear in the agent chain")
            registry.get(name)
        self.registry, self.chain = registry, tuple(chain)

    def build(self, wrap, controller):
        graph = StateGraph(WorkflowState)
        for name in self.chain:
            graph.add_node(name, wrap(self.registry.get(name)))
        graph.add_node("controller", controller)
        graph.add_edge(START, self.chain[0])
        for left, right in zip(self.chain, self.chain[1:]):
            graph.add_conditional_edges(
                left, lambda s: "stop" if s.error else "next", {"stop": "controller", "next": right}
            )
        graph.add_edge(self.chain[-1], "controller")
        graph.add_conditional_edges(
            "controller", lambda s: s.route, {"generation": self.chain[0], "end": END}
        )
        return graph.compile()
