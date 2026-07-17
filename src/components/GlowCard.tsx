import React, { useRef } from "react";

interface GlowCardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const GlowCard = ({ children, className = "", onClick }: GlowCardProps) => {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const card = cardRef.current;
    if (!card) return;

    const rect = card.getBoundingClientRect();
    card.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`);
    card.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`);
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onClick={onClick}
      className={`glow-card-hover glass-panel relative overflow-hidden rounded-xl border border-white/5 bg-zinc-950/40 p-5 transition-all duration-300 ${onClick ? 'cursor-pointer hover:border-white/10' : ''} ${className}`}
    >
      <div className="absolute inset-0 pixel-grid pointer-events-none opacity-20" />
      <div className="relative z-10 h-full w-full">{children}</div>
    </div>
  );
};
