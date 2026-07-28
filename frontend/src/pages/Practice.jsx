import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  MousePointer2,
  Square,
  Circle,
  Diamond,
  Database,
  Hexagon,
  Cloud,
  Minus,
  ArrowUpRight,
  Type,
  Trash2,
  Undo2,
  Redo2,
  Download,
  Send,
  GripVertical,
  X,
  MessageSquare,
} from "lucide-react";
import api from "../auth/auth";

const COLORS = ["#1e1e2e", "#e03131", "#2f9e44", "#1971c2", "#f08c00", "#9c36b5", "#495057"];
const STROKE_WIDTHS = [2, 4, 6];
const MIN_SIZE = 12;
const SHAPE_TYPES = ["rect", "ellipse", "diamond", "hexagon", "cylinder", "cloud"];
const BOARD_WIDTH = 3000;
const BOARD_HEIGHT = 2000;

let idCounter = 1;
const nextId = () => `el-${idCounter++}`;

function normalizeRect(el) {
  const x = Math.min(el.x, el.x2);
  const y = Math.min(el.y, el.y2);
  const width = Math.max(Math.abs(el.x2 - el.x), MIN_SIZE);
  const height = Math.max(Math.abs(el.y2 - el.y), MIN_SIZE);
  const { x2, y2, ...rest } = el;
  return { ...rest, x, y, width, height };
}

function getBBox(el) {
  // Used only for the selection outline / resize handles on already-
  // committed elements — by the time something is selectable,
  // normalizeRect() has already run, so width/height always exist here.
  if (el.type === "line" || el.type === "arrow") {
    return {
      x: Math.min(el.x, el.x2),
      y: Math.min(el.y, el.y2),
      width: Math.abs(el.x2 - el.x),
      height: Math.abs(el.y2 - el.y),
    };
  }
  return { x: el.x, y: el.y, width: el.width, height: el.height };
}

function getShapeBox(el) {
  // FIX: while a shape is actively being drawn (pointerDown → pointerUp),
  // the element only has x/y/x2/y2 — width/height don't exist until
  // normalizeRect() runs on pointer-up. Every shape branch below reads
  // el.width/el.height directly, so during the drag that's `undefined`,
  // and undefined / 2 is NaN — which is exactly what React was warning
  // about (cx/cy/rx/ry etc. all NaN on every drag frame). This helper
  // derives a valid box from x/x2/y/y2 whenever width/height aren't set
  // yet, so shapes render correctly *while* being drawn, not just after.
  if (el.width !== undefined && el.height !== undefined) {
    return { x: el.x, y: el.y, width: el.width, height: el.height };
  }
  const x = Math.min(el.x, el.x2);
  const y = Math.min(el.y, el.y2);
  const width = Math.abs(el.x2 - el.x);
  const height = Math.abs(el.y2 - el.y);
  return { x, y, width, height };
}

function arrowHead(x1, y1, x2, y2, size = 14, spread = 0.45) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const p1 = [
    x2 - size * Math.cos(angle - spread),
    y2 - size * Math.sin(angle - spread),
  ];
  const p2 = [
    x2 - size * Math.cos(angle + spread),
    y2 - size * Math.sin(angle + spread),
  ];
  return `${x2},${y2} ${p1[0]},${p1[1]} M ${x2},${y2} L ${p2[0]},${p2[1]}`;
}

export default function Whiteboard({ sessionId, onFeedback }) {
  const [elements, setElements] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [tool, setTool] = useState("select");
  const [color, setColor] = useState(COLORS[0]);
  const [strokeWidth, setStrokeWidth] = useState(2);
  const [fillOn, setFillOn] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [reviewStatus, setReviewStatus] = useState("idle"); // idle | sending | sent | error

  const [history, setHistory] = useState([[]]);
  const [historyIndex, setHistoryIndex] = useState(0);

  const svgRef = useRef(null);
  const dragRef = useRef(null);
  const textAreaRef = useRef(null);

  // ---- FEEDBACK PANEL (draggable, freely positionable) ----
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackVisible, setFeedbackVisible] = useState(false);
  const [feedbackPos, setFeedbackPos] = useState({ x: 24, y: 90 });

  const commit = useCallback((newElements) => {
    setElements(newElements);
    setHistory((h) => {
      const trimmed = h.slice(0, historyIndex + 1);
      return [...trimmed, newElements];
    });
    setHistoryIndex((i) => i + 1);
  }, [historyIndex]);

  const undo = () => {
    if (historyIndex === 0) return;
    const newIndex = historyIndex - 1;
    setHistoryIndex(newIndex);
    setElements(history[newIndex]);
    setSelectedId(null);
  };

  const redo = () => {
    if (historyIndex >= history.length - 1) return;
    const newIndex = historyIndex + 1;
    setHistoryIndex(newIndex);
    setElements(history[newIndex]);
    setSelectedId(null);
  };

  const getPoint = (e) => {
    const rect = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const selected = elements.find((el) => el.id === selectedId) || null;

  const updateSelectedStyle = (patch) => {
    if (!selectedId) return;
    const updated = elements.map((el) =>
      el.id === selectedId ? { ...el, ...patch } : el
    );
    commit(updated);
  };

  // ---- Pointer handlers (canvas drawing) ----
  const onBackgroundPointerDown = (e) => {
    const point = getPoint(e);

    if (tool === "select") {
      setSelectedId(null);
      return;
    }

    if (tool === "text") {
      const el = {
        id: nextId(),
        type: "text",
        x: point.x,
        y: point.y,
        width: 220,
        height: 32,
        text: "",
        color,
        fontSize: 20,
      };
      const updated = [...elements, el];
      commit(updated);
      setSelectedId(el.id);
      setEditingId(el.id);
      setTool("select");
      return;
    }

    const el = {
      id: nextId(),
      type: tool,
      x: point.x,
      y: point.y,
      x2: point.x,
      y2: point.y,
      color,
      strokeWidth,
      fill: fillOn,
    };
    setElements((prev) => [...prev, el]);
    dragRef.current = { mode: "draw", id: el.id };
  };

  const onElementPointerDown = (e, el) => {
    e.stopPropagation();
    if (tool !== "select") return;
    const point = getPoint(e);
    setSelectedId(el.id);
    dragRef.current = {
      mode: "move",
      id: el.id,
      startX: point.x,
      startY: point.y,
      orig: { ...el },
    };
  };

  const onHandlePointerDown = (e, handle) => {
    e.stopPropagation();
    const point = getPoint(e);
    dragRef.current = {
      mode: "resize",
      id: selectedId,
      handle,
      startX: point.x,
      startY: point.y,
      orig: { ...selected },
    };
  };

  const onPointerMove = (e) => {
    const drag = dragRef.current;
    if (!drag) return;
    const point = getPoint(e);

    if (drag.mode === "draw") {
      setElements((prev) =>
        prev.map((el) =>
          el.id === drag.id ? { ...el, x2: point.x, y2: point.y } : el
        )
      );
      return;
    }

    if (drag.mode === "move") {
      const dx = point.x - drag.startX;
      const dy = point.y - drag.startY;
      setElements((prev) =>
        prev.map((el) => {
          if (el.id !== drag.id) return el;
          const o = drag.orig;
          if (el.type === "line" || el.type === "arrow") {
            return { ...el, x: o.x + dx, y: o.y + dy, x2: o.x2 + dx, y2: o.y2 + dy };
          }
          return { ...el, x: o.x + dx, y: o.y + dy };
        })
      );
      return;
    }

    if (drag.mode === "resize") {
      const dx = point.x - drag.startX;
      const dy = point.y - drag.startY;
      const o = drag.orig;
      setElements((prev) =>
        prev.map((el) => {
          if (el.id !== drag.id) return el;
          if (el.type === "line" || el.type === "arrow") {
            if (drag.handle === "start") {
              return { ...el, x: o.x + dx, y: o.y + dy };
            }
            return { ...el, x2: o.x2 + dx, y2: o.y2 + dy };
          }
          let { x, y, width, height } = o;
          if (drag.handle.includes("w")) {
            width = Math.max(o.width - dx, MIN_SIZE);
            x = o.x + (o.width - width);
          }
          if (drag.handle.includes("e")) {
            width = Math.max(o.width + dx, MIN_SIZE);
          }
          if (drag.handle.includes("n")) {
            height = Math.max(o.height - dy, MIN_SIZE);
            y = o.y + (o.height - height);
          }
          if (drag.handle.includes("s")) {
            height = Math.max(o.height + dy, MIN_SIZE);
          }
          return { ...el, x, y, width, height };
        })
      );
    }
  };

  const onPointerUp = () => {
    const drag = dragRef.current;
    if (!drag) return;
    dragRef.current = null;

    if (drag.mode === "draw") {
      const updated = elements.map((el) => {
        if (el.id !== drag.id) return el;
        if (SHAPE_TYPES.includes(el.type)) {
          return normalizeRect(el);
        }
        return el;
      });
      commit(updated);
      setSelectedId(drag.id);
      setTool("select");
    } else {
      commit(elements);
    }
  };

  // ---- Text editing ----
  const startEditing = (el) => {
    setSelectedId(el.id);
    setEditingId(el.id);
  };

  useEffect(() => {
    if (editingId && textAreaRef.current) {
      textAreaRef.current.focus();
      textAreaRef.current.select();
    }
  }, [editingId]);

  const finishEditing = (text) => {
    setEditingId((currentEditingId) => {
      if (currentEditingId) {
        setElements((prevElements) => {
          const updated = prevElements.map((el) =>
            el.id === currentEditingId ? { ...el, text } : el
          );
          setHistory((h) => {
            const trimmed = h.slice(0, historyIndex + 1);
            return [...trimmed, updated];
          });
          setHistoryIndex((i) => i + 1);
          return updated;
        });
      }
      return null;
    });
  };

  // ---- Keyboard shortcuts ----
  useEffect(() => {
    const handler = (e) => {
      if (editingId) return;
      const tag = document.activeElement?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT") return;

      if ((e.key === "Delete" || e.key === "Backspace") && selectedId) {
        const updated = elements.filter((el) => el.id !== selectedId);
        commit(updated);
        setSelectedId(null);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      } else if (e.key === "v" || e.key === "1") setTool("select");
      else if (e.key === "r" || e.key === "2") setTool("rect");
      else if (e.key === "o" || e.key === "3") setTool("ellipse");
      else if (e.key === "l" || e.key === "4") setTool("line");
      else if (e.key === "a" || e.key === "5") setTool("arrow");
      else if (e.key === "t" || e.key === "6") setTool("text");
      else if (e.key === "d" || e.key === "7") setTool("diamond");
      else if (e.key === "y" || e.key === "8") setTool("cylinder");
      else if (e.key === "h" || e.key === "9") setTool("hexagon");
      else if (e.key === "u" || e.key === "0") setTool("cloud");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const clearCanvas = () => {
    commit([]);
    setSelectedId(null);
  };

  const exportSVG = () => {
    const svg = svgRef.current.cloneNode(true);
    svg.querySelectorAll("[data-ui-only]").forEach((n) => n.remove());
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svg);
    const blob = new Blob([source], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "whiteboard.svg";
    a.click();
    URL.revokeObjectURL(url);
  };

  // ---- Review: snapshot canvas as PNG and POST it to the tutor graph ----
  const handleReview = async () => {
    if (!sessionId) {
      console.error("No active session_id — cannot submit whiteboard.");
      setReviewStatus("error");
      setTimeout(() => setReviewStatus("idle"), 2500);
      return;
    }

    setReviewStatus("sending");
    try {
      const svgEl = svgRef.current.cloneNode(true);
      svgEl.querySelectorAll("[data-ui-only]").forEach((n) => n.remove());
      svgEl.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      svgEl.setAttribute("width", String(BOARD_WIDTH));
      svgEl.setAttribute("height", String(BOARD_HEIGHT));

      const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      bg.setAttribute("x", "0");
      bg.setAttribute("y", "0");
      bg.setAttribute("width", String(BOARD_WIDTH));
      bg.setAttribute("height", String(BOARD_HEIGHT));
      bg.setAttribute("fill", "#ffffff");
      svgEl.insertBefore(bg, svgEl.firstChild);

      const svgString = new XMLSerializer().serializeToString(svgEl);
      const svgBase64 = btoa(unescape(encodeURIComponent(svgString)));
      const svgDataUrl = "data:image/svg+xml;base64," + svgBase64;

      const pngBlob = await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement("canvas");
          canvas.width = BOARD_WIDTH;
          canvas.height = BOARD_HEIGHT;
          const ctx = canvas.getContext("2d");
          if (!ctx) return reject(new Error("Canvas context unavailable"));
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(
            (blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))),
            "image/png"
          );
        };
        img.onerror = reject;
        img.src = svgDataUrl;
      });

      const formData = new FormData();
      formData.append("image", pngBlob, "whiteboard.png");

      const res = await api.post(
        `api/system-design/session/${sessionId}/submit`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      const feedback = res.data?.feedback_text;

      if (feedback) {
        setFeedbackText(feedback);
        setFeedbackVisible(true);
        if (onFeedback) onFeedback(feedback);
      }

      setReviewStatus("sent");
    } catch (err) {
      console.error("Review submit failed:", err);
      setReviewStatus("error");
    } finally {
      setTimeout(() => setReviewStatus("idle"), 2500);
    }
  };

  // ---- Feedback panel drag handling ----
  const handleFeedbackDragStart = (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const origX = feedbackPos.x;
    const origY = feedbackPos.y;

    const handleMove = (moveEvent) => {
      const dx = moveEvent.clientX - startX;
      const dy = moveEvent.clientY - startY;
      setFeedbackPos({
        x: Math.max(0, origX + dx),
        y: Math.max(0, origY + dy),
      });
    };
    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  };

  const tools = [
    { id: "select", icon: MousePointer2, label: "Select (V)" },
    { id: "rect", icon: Square, label: "Service / Process box (R)" },
    { id: "ellipse", icon: Circle, label: "Node / Entity (O)" },
    { id: "diamond", icon: Diamond, label: "Decision / Load balancer (D)" },
    { id: "cylinder", icon: Database, label: "Database (Y)" },
    { id: "hexagon", icon: Hexagon, label: "Queue / Cache (H)" },
    { id: "cloud", icon: Cloud, label: "External / Cloud service (U)" },
    { id: "line", icon: Minus, label: "Line (L)" },
    { id: "arrow", icon: ArrowUpRight, label: "Arrow (A)" },
    { id: "text", icon: Type, label: "Text (T)" },
  ];

  const reviewLabel =
    reviewStatus === "sending"
      ? "Sending..."
      : reviewStatus === "sent"
      ? "Sent ✓"
      : reviewStatus === "error"
      ? "Failed ✕"
      : "Review";

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100vh",
        background: "#fafafa",
        overflow: "hidden",
        fontFamily:
          "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
        userSelect: dragRef.current ? "none" : "auto",
      }}
    >
      {/* Scrollable board */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          overflow: "auto",
        }}
      >
        <svg
          ref={svgRef}
          width={BOARD_WIDTH}
          height={BOARD_HEIGHT}
          viewBox={`0 0 ${BOARD_WIDTH} ${BOARD_HEIGHT}`}
          style={{
            display: "block",
            cursor: tool === "select" ? "default" : "crosshair",
            background: "#fafafa",
          }}
          onPointerDown={onBackgroundPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <defs>
            <pattern id="dotgrid" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="#00000018" />
            </pattern>
          </defs>
          <rect x="0" y="0" width="100%" height="100%" fill="url(#dotgrid)" />

          {elements.map((el) => {
            const isSelected = el.id === selectedId;
            // FIX: `key` no longer lives in this spread object — React
            // requires `key` to be a literal JSX attribute on each element,
            // not passed via {...spread}. It's applied directly below.
            const commonProps = {
              onPointerDown: (e) => onElementPointerDown(e, el),
              onDoubleClick: () => el.type === "text" && startEditing(el),
            };

            if (el.type === "rect") {
              const { x, y, width, height } = getShapeBox(el);
              return (
                <rect
                  key={el.id}
                  {...commonProps}
                  x={x}
                  y={y}
                  width={width}
                  height={height}
                  rx={4}
                  stroke={el.color}
                  strokeWidth={el.strokeWidth}
                  fill={el.fill ? el.color + "33" : "transparent"}
                />
              );
            }
            if (el.type === "ellipse") {
              const { x, y, width, height } = getShapeBox(el);
              return (
                <ellipse
                  key={el.id}
                  {...commonProps}
                  cx={x + width / 2}
                  cy={y + height / 2}
                  rx={width / 2}
                  ry={height / 2}
                  stroke={el.color}
                  strokeWidth={el.strokeWidth}
                  fill={el.fill ? el.color + "33" : "transparent"}
                />
              );
            }
            if (el.type === "diamond") {
              const { x, y, width, height } = getShapeBox(el);
              const cx = x + width / 2;
              const cy = y + height / 2;
              const points = `${cx},${y} ${x + width},${cy} ${cx},${y + height} ${x},${cy}`;
              return (
                <polygon
                  key={el.id}
                  {...commonProps}
                  points={points}
                  stroke={el.color}
                  strokeWidth={el.strokeWidth}
                  fill={el.fill ? el.color + "33" : "transparent"}
                />
              );
            }
            if (el.type === "hexagon") {
              const { x, y, width: w, height: h } = getShapeBox(el);
              const points = `${x + w * 0.25},${y} ${x + w * 0.75},${y} ${x + w},${y + h / 2} ${x + w * 0.75},${y + h} ${x + w * 0.25},${y + h} ${x},${y + h / 2}`;
              return (
                <polygon
                  key={el.id}
                  {...commonProps}
                  points={points}
                  stroke={el.color}
                  strokeWidth={el.strokeWidth}
                  fill={el.fill ? el.color + "33" : "transparent"}
                />
              );
            }
            if (el.type === "cylinder") {
              const { x, y, width: w, height: h } = getShapeBox(el);
              const rx = w / 2;
              const ry = Math.max(Math.min(h * 0.18, w * 0.25), 6);
              const bodyPath = `M ${x} ${y + ry} L ${x} ${y + h - ry} A ${rx} ${ry} 0 0 0 ${x + w} ${y + h - ry} L ${x + w} ${y + ry} A ${rx} ${ry} 0 0 0 ${x} ${y + ry} Z`;
              return (
                <g key={el.id} {...commonProps}>
                  <path
                    d={bodyPath}
                    stroke={el.color}
                    strokeWidth={el.strokeWidth}
                    fill={el.fill ? el.color + "33" : "transparent"}
                  />
                  <ellipse
                    cx={x + w / 2}
                    cy={y + ry}
                    rx={rx}
                    ry={ry}
                    stroke={el.color}
                    strokeWidth={el.strokeWidth}
                    fill={el.fill ? el.color + "33" : "transparent"}
                  />
                </g>
              );
            }
            if (el.type === "cloud") {
              const { x, y, width: w, height: h } = getShapeBox(el);
              const sx = w / 70;
              const sy = h / 47;
              const d =
                "M20,45 C9,45 0,36.5 0,26 C0,16.5 7,8.5 16.5,7 C19,3 25,0 32,0 C40,0 47,3.5 50.5,9.5 C61,10 70,18 70,28 C70,38.5 61,47 50,47 Z";
              return (
                <path
                  key={el.id}
                  {...commonProps}
                  d={d}
                  transform={`translate(${x},${y}) scale(${sx},${sy})`}
                  stroke={el.color}
                  strokeWidth={el.strokeWidth}
                  vectorEffect="non-scaling-stroke"
                  fill={el.fill ? el.color + "33" : "transparent"}
                />
              );
            }
            if (el.type === "line" || el.type === "arrow") {
              return (
                <g key={el.id} {...commonProps}>
                  <line
                    x1={el.x}
                    y1={el.y}
                    x2={el.x2}
                    y2={el.y2}
                    stroke={el.color}
                    strokeWidth={el.strokeWidth}
                  />
                  {el.type === "arrow" && (
                    <path
                      d={`M ${arrowHead(el.x, el.y, el.x2, el.y2)}`}
                      stroke={el.color}
                      strokeWidth={el.strokeWidth}
                      fill="none"
                      strokeLinecap="round"
                    />
                  )}
                  <line
                    x1={el.x}
                    y1={el.y}
                    x2={el.x2}
                    y2={el.y2}
                    stroke="transparent"
                    strokeWidth={Math.max(el.strokeWidth, 16)}
                  />
                </g>
              );
            }
            if (el.type === "text") {
              if (editingId === el.id) return null;
              return (
                <text
                  key={el.id}
                  {...commonProps}
                  x={el.x}
                  y={el.y + el.fontSize}
                  fontSize={el.fontSize}
                  fill={el.color}
                  style={{ whiteSpace: "pre" }}
                >
                  {(el.text || "Double-click to edit").split("\n").map((line, i) => (
                    <tspan key={i} x={el.x} dy={i === 0 ? 0 : el.fontSize * 1.2}>
                      {line}
                    </tspan>
                  ))}
                </text>
              );
            }
            return null;
          })}

          {/* Selection outline + handles */}
          {selected && !editingId && (() => {
            const box = getBBox(selected);
            if (selected.type === "line" || selected.type === "arrow") {
              return (
                <g data-ui-only="true">
                  <circle
                    cx={selected.x}
                    cy={selected.y}
                    r={6}
                    fill="#fff"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    onPointerDown={(e) => onHandlePointerDown(e, "start")}
                    style={{ cursor: "move" }}
                  />
                  <circle
                    cx={selected.x2}
                    cy={selected.y2}
                    r={6}
                    fill="#fff"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    onPointerDown={(e) => onHandlePointerDown(e, "end")}
                    style={{ cursor: "move" }}
                  />
                </g>
              );
            }
            const handles = [
              { name: "nw", x: box.x, y: box.y, cursor: "nwse-resize" },
              { name: "ne", x: box.x + box.width, y: box.y, cursor: "nesw-resize" },
              { name: "sw", x: box.x, y: box.y + box.height, cursor: "nesw-resize" },
              { name: "se", x: box.x + box.width, y: box.y + box.height, cursor: "nwse-resize" },
            ];
            return (
              <g data-ui-only="true">
                <rect
                  x={box.x - 4}
                  y={box.y - 4}
                  width={box.width + 8}
                  height={box.height + 8}
                  fill="none"
                  stroke="#4f46e5"
                  strokeDasharray="4 3"
                  strokeWidth={1.5}
                />
                {handles.map((h) => (
                  <rect
                    key={h.name}
                    x={h.x - 5}
                    y={h.y - 5}
                    width={10}
                    height={10}
                    fill="#fff"
                    stroke="#4f46e5"
                    strokeWidth={1.5}
                    style={{ cursor: h.cursor }}
                    onPointerDown={(e) => onHandlePointerDown(e, h.name)}
                  />
                ))}
              </g>
            );
          })()}

          {/* Inline text editor */}
          {editingId && selected && selected.type === "text" && (
            <foreignObject
              x={selected.x}
              y={selected.y}
              width={Math.max(selected.width, 220)}
              height={Math.max(selected.height, 60)}
            >
              <textarea
                ref={textAreaRef}
                defaultValue={selected.text}
                onPointerDown={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => e.stopPropagation()}
                onBlur={(e) => finishEditing(e.target.value)}
                onKeyDown={(e) => {
                  e.stopPropagation();
                  if (e.key === "Escape") finishEditing(e.target.value);
                }}
                style={{
                  width: "100%",
                  height: "100%",
                  fontSize: selected.fontSize,
                  color: selected.color,
                  border: "1px dashed #4f46e5",
                  outline: "none",
                  background: "rgba(255,255,255,0.95)",
                  resize: "both",
                  fontFamily: "inherit",
                  padding: 2,
                }}
              />
            </foreignObject>
          )}
        </svg>
      </div>

      {/* Top toolbar (fixed above the scrollable board) */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          display: "flex",
          gap: 4,
          background: "#ffffff",
          borderRadius: 14,
          padding: 6,
          boxShadow: "0 2px 10px rgba(0,0,0,0.12)",
          flexWrap: "wrap",
          maxWidth: "92vw",
        }}
      >
        {tools.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            title={label}
            onClick={() => setTool(id)}
            style={{
              width: 40,
              height: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "none",
              borderRadius: 10,
              cursor: "pointer",
              background: tool === id ? "#eef2ff" : "transparent",
              color: tool === id ? "#4f46e5" : "#343a40",
            }}
          >
            <Icon size={20} />
          </button>
        ))}
        <div style={{ width: 1, background: "#e9ecef", margin: "4px 4px" }} />
        <button
          title="Undo (Ctrl+Z)"
          onClick={undo}
          disabled={historyIndex === 0}
          style={iconBtnStyle(historyIndex === 0)}
        >
          <Undo2 size={20} />
        </button>
        <button
          title="Redo (Ctrl+Shift+Z)"
          onClick={redo}
          disabled={historyIndex >= history.length - 1}
          style={iconBtnStyle(historyIndex >= history.length - 1)}
        >
          <Redo2 size={20} />
        </button>
        <div style={{ width: 1, background: "#e9ecef", margin: "4px 4px" }} />
        <button title="Export SVG" onClick={exportSVG} style={iconBtnStyle(false)}>
          <Download size={20} />
        </button>
        <button title="Clear canvas" onClick={clearCanvas} style={iconBtnStyle(false)}>
          <Trash2 size={20} />
        </button>
        <div style={{ width: 1, background: "#e9ecef", margin: "4px 4px" }} />
        <button
          title="Submit whiteboard for AI review"
          onClick={handleReview}
          disabled={reviewStatus === "sending"}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            height: 40,
            padding: "0 14px",
            border: "none",
            borderRadius: 10,
            cursor: reviewStatus === "sending" ? "default" : "pointer",
            background:
              reviewStatus === "sent"
                ? "#ebfbee"
                : reviewStatus === "error"
                ? "#fff5f5"
                : "#eef2ff",
            color:
              reviewStatus === "sent"
                ? "#2f9e44"
                : reviewStatus === "error"
                ? "#e03131"
                : "#4f46e5",
            fontSize: 13,
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          <Send size={16} />
          {reviewLabel}
        </button>

        {!feedbackVisible && feedbackText && (
          <button
            title="Show last feedback"
            onClick={() => setFeedbackVisible(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              height: 40,
              padding: "0 14px",
              border: "none",
              borderRadius: 10,
              cursor: "pointer",
              background: "#fff7e6",
              color: "#e8590c",
              fontSize: 13,
              fontWeight: 600,
              whiteSpace: "nowrap",
            }}
          >
            <MessageSquare size={16} />
            Feedback
          </button>
        )}
      </div>

      {/* Style panel */}
      {(tool !== "select" || selected) && (
        <div
          style={{
            position: "absolute",
            top: 16,
            left: 16,
            zIndex: 10,
            background: "#ffffff",
            borderRadius: 14,
            padding: 14,
            boxShadow: "0 2px 10px rgba(0,0,0,0.12)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            width: 160,
          }}
        >
          <div>
            <div style={labelStyle}>Stroke</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    setColor(c);
                    if (selected) updateSelectedStyle({ color: c });
                  }}
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 6,
                    background: c,
                    border:
                      (selected ? selected.color : color) === c
                        ? "2px solid #4f46e5"
                        : "1px solid #dee2e6",
                    cursor: "pointer",
                  }}
                />
              ))}
            </div>
          </div>

          {tool !== "text" && (!selected || selected.type !== "text") && (
            <div>
              <div style={labelStyle}>Stroke width</div>
              <div style={{ display: "flex", gap: 6 }}>
                {STROKE_WIDTHS.map((w) => (
                  <button
                    key={w}
                    onClick={() => {
                      setStrokeWidth(w);
                      if (selected) updateSelectedStyle({ strokeWidth: w });
                    }}
                    style={{
                      flex: 1,
                      height: 28,
                      borderRadius: 8,
                      border: "1px solid #dee2e6",
                      background:
                        (selected ? selected.strokeWidth : strokeWidth) === w
                          ? "#eef2ff"
                          : "#fff",
                      cursor: "pointer",
                    }}
                  >
                    <div
                      style={{
                        height: w,
                        background: "#343a40",
                        borderRadius: 2,
                        margin: "0 8px",
                      }}
                    />
                  </button>
                ))}
              </div>
            </div>
          )}

          {(SHAPE_TYPES.includes(tool) || SHAPE_TYPES.includes(selected?.type)) && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                id="fillToggle"
                checked={selected ? !!selected.fill : fillOn}
                onChange={(e) => {
                  setFillOn(e.target.checked);
                  if (selected) updateSelectedStyle({ fill: e.target.checked });
                }}
              />
              <label htmlFor="fillToggle" style={labelStyle}>
                Fill shape
              </label>
            </div>
          )}
        </div>
      )}

      {/* Draggable feedback panel — freely positionable anywhere on screen */}
      {feedbackVisible && feedbackText && (
        <div
          style={{
            position: "absolute",
            top: feedbackPos.y,
            left: feedbackPos.x,
            zIndex: 20,
            width: 320,
            maxHeight: "60vh",
            background: "#ffffff",
            borderRadius: 14,
            boxShadow: "0 8px 28px rgba(0,0,0,0.18)",
            border: "1px solid #e9ecef",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div
            onPointerDown={handleFeedbackDragStart}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              background: "#f8f9fa",
              borderBottom: "1px solid #e9ecef",
              cursor: "grab",
              userSelect: "none",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <GripVertical size={16} color="#adb5bd" />
              <MessageSquare size={15} color="#4f46e5" />
              <span style={{ fontSize: 13, fontWeight: 700, color: "#1e1e2e" }}>
                AI Feedback
              </span>
            </div>
            <button
              onClick={() => setFeedbackVisible(false)}
              title="Close"
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#868e96",
                padding: 4,
                borderRadius: 6,
              }}
            >
              <X size={16} />
            </button>
          </div>

          <div
            style={{
              padding: 14,
              overflowY: "auto",
              fontSize: 13,
              lineHeight: 1.55,
              color: "#343a40",
              whiteSpace: "pre-wrap",
            }}
          >
            {feedbackText}
          </div>
        </div>
      )}

      <div
        style={{
          position: "absolute",
          bottom: 12,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          fontSize: 12,
          color: "#adb5bd",
          background: "#fafafacc",
          padding: "2px 10px",
          borderRadius: 8,
          textAlign: "center",
        }}
      >
        V select · R box · O node · D decision · Y database · H queue · U cloud · L line · A arrow · T text · Del delete · Ctrl+Z undo
      </div>
    </div>
  );
}

function iconBtnStyle(disabled) {
  return {
    width: 40,
    height: 40,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "none",
    borderRadius: 10,
    cursor: disabled ? "default" : "pointer",
    background: "transparent",
    color: disabled ? "#ced4da" : "#343a40",
  };
}

const labelStyle = {
  fontSize: 11,
  color: "#868e96",
  marginBottom: 4,
  fontWeight: 500,
};