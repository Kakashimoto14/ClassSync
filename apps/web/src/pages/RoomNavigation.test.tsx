import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DevelopmentRoleContext } from '../auth/development-role-context';
import { routeDefinitions } from '../routes/route-config';
import { ProductScreenPage } from './ProductScreenPage';

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
});

describe('room card destinations', () => {
  it.each(['student', 'teacher', 'administrator'] as const)(
    'shows only real %s room detail actions',
    (role) => {
      const definition = routeDefinitions.find(
        (item) => item.id === `${role}.${role === 'teacher' ? 'find-room' : 'rooms'}`,
      )!;
      render(
        <MemoryRouter initialEntries={[definition.path]}>
          <DevelopmentRoleContext.Provider value={{ role, startDemo: vi.fn(), signOut: vi.fn() }}>
            <ProductScreenPage definition={definition} />
          </DevelopmentRoleContext.Provider>
        </MemoryRouter>,
      );
      const main = screen.getByRole('main');
      const cards = within(main).getAllByRole('article');
      expect(cards).toHaveLength(3);
      expect(within(main).getAllByText('Resource active')).toHaveLength(2);
      expect(within(main).queryByText('Available')).not.toBeInTheDocument();
      const links = within(main).queryAllByRole('link', { name: 'View room details' });
      expect(links).toHaveLength(role === 'administrator' ? 1 : 0);
      if (role === 'administrator') {
        expect(links[0]).toHaveAttribute('href', '/admin/rooms/detail');
        expect(within(cards[0]).getByRole('heading', { name: 'SCI-218' })).toBeInTheDocument();
      }
      fireEvent.change(within(main).getByRole('combobox', { name: 'Building' }), {
        target: { value: 'Computing Building' },
      });
      expect(within(main).getAllByRole('article')).toHaveLength(1);
      expect(within(main).getByRole('heading', { name: 'LAB-04' })).toBeInTheDocument();
      expect(
        within(main).queryByRole('link', { name: 'View room details' }),
      ).not.toBeInTheDocument();
    },
  );
});
