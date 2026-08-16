"use client";

// leaflet.css is imported globally in globals.css so it's guaranteed to be
// present before Leaflet computes any layout, even for this dynamically
// code-split, client-only chunk.
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMap } from "react-leaflet";
import { Component, useMemo, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { NodeState, NetworkEdge } from "@/lib/api";
import { riskColor, riskLabel, fmtNumber } from "@/lib/utils";

// Non-subdomain-sharded host. The {s}.basemaps.cartocdn.com pattern (a/b/c/d
// subdomains) is a common shape that ad-blockers, corporate SSL-inspecting
// proxies, and DNS-level filters flag as tracker/CDN-like traffic and either
// drop or intercept with a non-image response, which the browser then
// CORB-blocks from ever reaching the page. The single-host form below is
// the same CARTO service without that pattern.
const DARK_TILES = "https://basemaps.cartocdn.com/dark_matter/{z}/{x}/{y}{r}.png";

function FitBounds({ nodes }: { nodes: NodeState[] }) {
  const map = useMap();
  useEffect(() => {
    if (!nodes.length) return;
    const bounds = nodes.map((n) => [n.lat, n.lon] as [number, number]);
    map.fitBounds(bounds, { padding: [30, 30] });
  }, [nodes, map]);
  return null;
}

/**
 * Confirmed via headless rendering: this map's container reliably measures
 * 0px tall on first mount (916 × 0) even though Leaflet itself initializes
 * fine and draws all markers/edges into the DOM. Leaflet only measures its
 * container once, at creation time; if that read happens a frame before the
 * surrounding flex/grid layout has finished settling (very common when a
 * dynamically-imported, client-only chunk mounts into a layout that's
 * simultaneously reflowing from sibling content, e.g. the explanation panel
 * populating), the 0×0 size sticks forever and nothing is ever painted.
 * A ResizeObserver + a couple of invalidateSize() calls after mount forces
 * Leaflet to re-measure once real layout is in place.
 */
function AutoResize() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();

    map.invalidateSize();
    const raf = requestAnimationFrame(() => map.invalidateSize());
    const t1 = setTimeout(() => map.invalidateSize(), 150);
    const t2 = setTimeout(() => map.invalidateSize(), 500);

    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(t1);
      clearTimeout(t2);
      ro.disconnect();
    };
  }, [map]);
  return null;
}

/**
 * React 19 (and React 18 Strict Mode) mounts, unmounts, then re-mounts every
 * component's effects once on first render. react-leaflet's <MapContainer>
 * creates its underlying Leaflet map instance in that first effect and never
 * cleans up the internal `_leaflet_id` marker Leaflet stamps onto the DOM
 * node, so the *second* (real) mount throws "Map container is already
 * initialized" — react-leaflet doesn't catch it, so React aborts rendering
 * that subtree and the map area is left permanently blank with no visible
 * error. See https://github.com/PaulLeCam/react-leaflet/issues/1133
 *
 * The fix: track the container div ourselves and, on every unmount, strip
 * the `_leaflet_id` Leaflet left behind so the next mount is treated as
 * fresh instead of colliding with a "ghost" map instance.
 */
function StrictModeSafeMap({
  children,
  ...props
}: import("react").ComponentProps<typeof MapContainer>) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  // Forces a clean remount if the guarded cleanup ever needs to recover from
  // an error thrown during the double-invoked first mount.
  const [instanceKey, setInstanceKey] = useState(0);

  useEffect(() => {
    return () => {
      const leafletEl = wrapperRef.current?.querySelector(
        ".leaflet-container"
      ) as (HTMLElement & { _leaflet_id?: number | null }) | null;
      if (leafletEl && leafletEl._leaflet_id != null) {
        leafletEl._leaflet_id = null;
      }
    };
  }, [instanceKey]);

  return (
    <div ref={wrapperRef} className="absolute inset-0">
      <MapErrorBoundary onRecover={() => setInstanceKey((k) => k + 1)}>
        <MapContainer key={instanceKey} {...props}>
          {children}
        </MapContainer>
      </MapErrorBoundary>
    </div>
  );
}

class MapErrorBoundary extends Component<
  { children: ReactNode; onRecover: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    // Give the DOM a tick to settle, then remount cleanly.
    setTimeout(() => {
      this.setState({ failed: false });
      this.props.onRecover();
    }, 0);
  }
  render() {
    if (this.state.failed) return null;
    return this.props.children;
  }
}

export function WorldMap({
  nodes,
  edges = [],
  onSelect,
  selected,
  showEdges = true,
}: {
  nodes: NodeState[];
  edges?: NetworkEdge[];
  onSelect?: (name: string) => void;
  selected?: string | null;
  showEdges?: boolean;
}) {
  const nodeByName = useMemo(() => {
    const m = new Map<string, NodeState>();
    nodes.forEach((n) => m.set(n.name, n));
    return m;
  }, [nodes]);

  const maxPop = useMemo(
    () => Math.max(1, ...nodes.map((n) => n.population_millions)),
    [nodes]
  );

  const drawnEdges = useMemo(() => {
    if (!showEdges) return [];
    // Only draw a legible subset: strongest / disrupted edges
    return edges
      .filter((e) => nodeByName.has(e.source) && nodeByName.has(e.target))
      .sort((a, b) => b.capacity - a.capacity)
      .slice(0, 120);
  }, [edges, nodeByName, showEdges]);

  return (
    <StrictModeSafeMap
      center={[15, 10]}
      zoom={2}
      minZoom={2}
      maxBounds={[[-85, -200], [85, 200]]}
      className="h-full w-full rounded-xl map-fallback-bg"
      scrollWheelZoom
      worldCopyJump
    >
      <TileLayer
        url={DARK_TILES}
        attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
        // If every tile request is blocked (ad-blocker, corporate proxy, DNS
        // filtering — see CORB errors in the browser's Network/Issues panel),
        // Leaflet just leaves those grid squares empty by default. The
        // .map-fallback-bg CSS class gives the container a faint graticule so
        // the area never looks like a broken/dead void, and node markers
        // below are unaffected either way since they're plain SVG, not tile
        // images.
        eventHandlers={{
          tileerror: () => {
            /* swallow — fallback background + markers still render */
          },
        }}
      />
      <FitBounds nodes={nodes} />
      <AutoResize />

      {drawnEdges.map((e, i) => {
        const s = nodeByName.get(e.source)!;
        const t = nodeByName.get(e.target)!;
        return (
          <Polyline
            key={`${e.source}-${e.target}-${i}`}
            positions={[
              [s.lat, s.lon],
              [t.lat, t.lon],
            ]}
            pathOptions={{
              color: e.active ? "#3FC7BE" : "#DB5A46",
              weight: e.active ? 0.6 : 1.1,
              opacity: e.active ? 0.18 : 0.5,
              dashArray: e.active ? undefined : "3 4",
            }}
          />
        );
      })}

      {nodes.map((n) => {
        const radius = 4 + 16 * Math.sqrt(n.population_millions / maxPop);
        const color = riskColor(n.food_security);
        const isSelected = selected === n.name;
        return (
          <CircleMarker
            key={n.id}
            center={[n.lat, n.lon]}
            radius={radius}
            pathOptions={{
              color: isSelected ? "#EDF2F6" : color,
              weight: isSelected ? 2 : 1,
              fillColor: color,
              fillOpacity: n.overload_food ? 0.85 : 0.55,
            }}
            eventHandlers={{
              click: () => onSelect?.(n.name),
            }}
          >
            <Tooltip direction="top" offset={[0, -radius]} opacity={0.95}>
              <div className="font-mono text-xs">
                <div className="font-semibold">{n.name}</div>
                <div>σ (food security): {n.food_security.toFixed(2)} — {riskLabel(n.food_security)}</div>
                <div>Population: {fmtNumber(n.population_millions * 1e6)}</div>
                {n.export_ban && <div className="text-red-400">Export ban active</div>}
                {n.overload_food && <div className="text-red-400">LFBB overload</div>}
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </StrictModeSafeMap>
  );
}
