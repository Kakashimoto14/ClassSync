import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Drawer } from './Drawer';

describe('Drawer', () => {
  it('focuses its close control and closes with Escape', () => {
    const onClose = vi.fn();
    render(
      <Drawer title="Student menu" onClose={onClose}>
        <p>Secondary navigation</p>
      </Drawer>,
    );

    expect(screen.getByRole('button', { name: 'Close drawer' })).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes from the backdrop but not from drawer content', () => {
    const onClose = vi.fn();
    render(
      <Drawer title="Student menu" onClose={onClose}>
        <p>Secondary navigation</p>
      </Drawer>,
    );

    fireEvent.mouseDown(screen.getByText('Secondary navigation'));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(document.querySelector('.drawer-overlay')!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('contains keyboard focus, locks the background, and restores focus on close', () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'Open menu';
    document.body.append(trigger);
    trigger.focus();
    const { unmount } = render(
      <Drawer title="Menu" onClose={() => undefined}>
        <a href="/student/settings">Settings</a>
      </Drawer>,
    );
    expect(trigger).toHaveAttribute('inert');
    expect(document.body.style.overflow).toBe('hidden');
    const close = screen.getByRole('button', { name: 'Close drawer' });
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(screen.getByRole('link', { name: 'Settings' })).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: 'Tab' });
    expect(close).toHaveFocus();
    unmount();
    expect(trigger).toHaveFocus();
    expect(trigger).not.toHaveAttribute('inert');
    expect(document.body.style.overflow).toBe('');
    trigger.remove();
  });
});
