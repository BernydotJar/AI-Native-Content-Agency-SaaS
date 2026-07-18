import { useEffect, useRef } from "react";

interface MeshNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const makeNode = (width: number, height: number): MeshNode => ({
  x: Math.random() * width,
  y: Math.random() * height,
  vx: (Math.random() - 0.5) * 0.28,
  vy: (Math.random() - 0.5) * 0.28,
});

export const CanvasBackground = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const pointer = { x: 0, y: 0, active: false };
    const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduceMotion = reduceMotionQuery.matches;
    let frameId = 0;
    let width = window.innerWidth;
    let height = window.innerHeight;
    let nodes: MeshNode[] = [];
    let accent = "hsla(200, 80%, 60%, 0.46)";

    const readAccent = () => {
      const styles = getComputedStyle(document.documentElement);
      const hue = styles.getPropertyValue("--primary-hue").trim() || "200";
      const saturation = styles.getPropertyValue("--primary-saturation").trim() || "80%";
      const lightness = styles.getPropertyValue("--primary-lightness").trim() || "60%";
      accent = `hsla(${hue}, ${saturation}, ${lightness}, 0.46)`;
    };

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);

      const targetCount = Math.min(92, Math.max(26, Math.floor((width * height) / 18_000)));
      if (nodes.length > targetCount) nodes = nodes.slice(0, targetCount);
      while (nodes.length < targetCount) nodes.push(makeNode(width, height));
    };

    const draw = (advance = true) => {
      context.clearRect(0, 0, width, height);

      for (const node of nodes) {
        if (advance) {
          node.x += node.vx;
          node.y += node.vy;

          if (node.x <= 0 || node.x >= width) node.vx *= -1;
          if (node.y <= 0 || node.y >= height) node.vy *= -1;

          if (pointer.active) {
            const dx = pointer.x - node.x;
            const dy = pointer.y - node.y;
            const distance = Math.hypot(dx, dy);
            if (distance > 0 && distance < 190) {
              node.x += (dx / distance) * 0.11;
              node.y += (dy / distance) * 0.11;
            }
          }
        }

        context.beginPath();
        context.arc(node.x, node.y, 1.05, 0, Math.PI * 2);
        context.fillStyle = accent;
        context.fill();
      }

      context.lineWidth = 0.5;
      for (let first = 0; first < nodes.length; first += 1) {
        for (let second = first + 1; second < nodes.length; second += 1) {
          const dx = nodes[first].x - nodes[second].x;
          const dy = nodes[first].y - nodes[second].y;
          const distance = Math.hypot(dx, dy);
          if (distance >= 125) continue;

          context.strokeStyle = `rgba(212, 212, 216, ${(1 - distance / 125) * 0.085})`;
          context.beginPath();
          context.moveTo(nodes[first].x, nodes[first].y);
          context.lineTo(nodes[second].x, nodes[second].y);
          context.stroke();
        }
      }
    };

    const animate = () => {
      draw(true);
      frameId = window.requestAnimationFrame(animate);
    };

    const start = () => {
      window.cancelAnimationFrame(frameId);
      if (document.hidden || reduceMotion) {
        draw(false);
        return;
      }
      animate();
    };

    const handlePointerMove = (event: PointerEvent) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = event.pointerType !== "touch";
    };
    const handlePointerLeave = () => { pointer.active = false; };
    const handleResize = () => { resize(); start(); };
    const handleMotionChange = (event: MediaQueryListEvent) => {
      reduceMotion = event.matches;
      start();
    };

    const styleObserver = new MutationObserver(() => readAccent());
    styleObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] });

    readAccent();
    resize();
    start();
    window.addEventListener("resize", handleResize);
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    document.addEventListener("pointerleave", handlePointerLeave);
    document.addEventListener("visibilitychange", start);
    reduceMotionQuery.addEventListener("change", handleMotionChange);

    return () => {
      window.cancelAnimationFrame(frameId);
      styleObserver.disconnect();
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("pointerleave", handlePointerLeave);
      document.removeEventListener("visibilitychange", start);
      reduceMotionQuery.removeEventListener("change", handleMotionChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0 h-full w-full opacity-55"
    />
  );
};
