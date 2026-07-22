import { useRef, useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { useModalDialog } from "./useModalDialog";

function Fixture() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const firstRef = useRef<HTMLButtonElement>(null);
  useModalDialog({
    open,
    onClose: () => setOpen(false),
    dialogRef,
    initialFocusRef: firstRef,
    returnFocusRef: triggerRef,
  });

  return (
    <>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>Abrir</button>
      {open && (
        <section ref={dialogRef} role="dialog" aria-label="Configuración">
          <button ref={firstRef} type="button">Primero</button>
          <button type="button">Último</button>
        </section>
      )}
    </>
  );
}

describe("useModalDialog", () => {
  it("keeps keyboard focus inside the modal in both directions", async () => {
    const user = userEvent.setup();
    render(<Fixture />);

    await user.click(screen.getByRole("button", { name: "Abrir" }));
    expect(screen.getByRole("button", { name: "Primero" })).toHaveFocus();

    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Último" })).toHaveFocus();

    await user.tab();
    expect(screen.getByRole("button", { name: "Primero" })).toHaveFocus();
  });

  it("closes with Escape and restores focus to the trigger", async () => {
    const user = userEvent.setup();
    render(<Fixture />);

    const trigger = screen.getByRole("button", { name: "Abrir" });
    await user.click(trigger);
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
