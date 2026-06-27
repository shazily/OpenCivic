"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LineageEdge, LineageNode } from "@/lib/api/types";

interface LineageGraphD3Props {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
}

function nodeTypeLabel(type: string): string {
  switch (type) {
    case "source":
      return "Source";
    case "connector":
      return "Connector";
    case "transform":
      return "Transform";
    case "dataset":
      return "Dataset";
    case "version":
      return "Version";
    default:
      return type;
  }
}

function nodeColor(type: string): string {
  switch (type) {
    case "source":
      return "var(--color-primary)";
    case "dataset":
      return "#0d9488";
    case "version":
      return "#7c3aed";
    case "connector":
      return "#ea580c";
    default:
      return "var(--color-foreground-muted)";
  }
}

export function LineageGraphD3({ nodes, edges }: LineageGraphD3Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) {
      return;
    }

    const width = 720;
    const height = Math.max(220, nodes.length * 70);
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const simulationNodes: SimNode[] = nodes.map((node) => ({
      id: node.id,
      label: node.label,
      type: node.type,
    }));

    const simulationLinks = edges.map((edge) => ({
      source: edge.from_node_id,
      target: edge.to_node_id,
    }));

    const simulation = d3
      .forceSimulation(simulationNodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, { source: string; target: string }>(simulationLinks)
          .id((d) => d.id)
          .distance(120),
      )
      .force("charge", d3.forceManyBody().strength(-400))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.05))
      .force("y", d3.forceY(height / 2).strength(0.05));

    const link = svg
      .append("g")
      .attr("stroke", "var(--color-border)")
      .attr("stroke-opacity", 0.8)
      .selectAll("line")
      .data(simulationLinks)
      .join("line")
      .attr("stroke-width", 1.5);

    const node = svg
      .append("g")
      .selectAll("g")
      .data(simulationNodes)
      .join("g");

    node
      .append("circle")
      .attr("r", 22)
      .attr("fill", (d) => nodeColor(d.type))
      .attr("opacity", 0.9);

    node
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 40)
      .attr("fill", "var(--color-foreground)")
      .attr("font-size", 11)
      .text((d) => (d.label.length > 24 ? `${d.label.slice(0, 22)}…` : d.label));

    node
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 4)
      .attr("fill", "#fff")
      .attr("font-size", 9)
      .attr("font-weight", 600)
      .text((d) => nodeTypeLabel(d.type).slice(0, 3).toUpperCase());

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => {
          const source = d.source as SimNode | string;
          return typeof source === "string"
            ? simulationNodes.find((n) => n.id === source)?.x ?? 0
            : source.x ?? 0;
        })
        .attr("y1", (d) => {
          const source = d.source as SimNode | string;
          return typeof source === "string"
            ? simulationNodes.find((n) => n.id === source)?.y ?? 0
            : source.y ?? 0;
        })
        .attr("x2", (d) => {
          const target = d.target as SimNode | string;
          return typeof target === "string"
            ? simulationNodes.find((n) => n.id === target)?.x ?? 0
            : target.x ?? 0;
        })
        .attr("y2", (d) => {
          const target = d.target as SimNode | string;
          return typeof target === "string"
            ? simulationNodes.find((n) => n.id === target)?.y ?? 0
            : target.y ?? 0;
        });

      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, edges]);

  if (nodes.length === 0) {
    return (
      <p className="text-sm text-[var(--color-foreground-muted)]">
        No lineage recorded for this dataset yet.
      </p>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Data lineage</CardTitle>
      </CardHeader>
      <CardContent>
        <svg
          ref={svgRef}
          className="mx-auto w-full max-w-3xl"
          role="img"
          aria-label="Interactive lineage graph"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {Array.from(new Set(nodes.map((n) => n.type))).map((type) => (
            <Badge key={type} variant="outline">
              {nodeTypeLabel(type)}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
