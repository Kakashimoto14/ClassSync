import { Button } from '../ui/Button';
import {
  roomFacilities,
  validMinimumCapacity,
  type RoomCriteria,
  type RoomRecord,
} from '../../lib/room-discovery';

export function RoomFilters({
  rooms,
  criteria,
  onChange,
  onReset,
  inventorySource,
  onInventoryChange,
}: {
  rooms: readonly RoomRecord[];
  criteria: RoomCriteria;
  onChange: (key: keyof RoomCriteria, value: string) => void;
  onReset: () => void;
  inventorySource: 'cdm' | 'demo';
  onInventoryChange: (value: string) => void;
}) {
  const active = Object.entries(criteria).filter(([, value]) => value !== '');
  const filterCount = active.filter(([key]) => key !== 'search').length;
  const options = (values: string[]) =>
    [...new Set(values)].sort().map((value) => <option key={value}>{value}</option>);
  const validCapacity = validMinimumCapacity(criteria.capacity);
  const hasMetadata = rooms.some((room) => room.resource);
  return (
    <section className="discovery-filters" aria-label="Filter rooms">
      <div className="discovery-filters__search">
        <label>
          Inventory
          <select
            value={inventorySource}
            onChange={(event) => onInventoryChange(event.target.value)}
          >
            <option value="cdm">CDM · Provisional</option>
            <option value="demo">Demo scenario</option>
          </select>
        </label>
        <label>
          Search rooms
          <input
            type="search"
            placeholder="Room name, number or alias"
            value={criteria.search}
            onChange={(event) => onChange('search', event.target.value)}
          />
        </label>
      </div>
      <details className="discovery-filters__details">
        <summary>Filters{filterCount > 0 && ` (${filterCount})`}</summary>
        <div className="discovery-filters__fields">
          <label>
            Building or area
            <select
              value={criteria.building}
              onChange={(event) => onChange('building', event.target.value)}
            >
              <option value="">All buildings / areas</option>
              {options(rooms.map((room) => room.building))}
            </select>
          </label>
          {hasMetadata && (
            <>
              <label>
                Minimum capacity
                <input
                  type="number"
                  min="1"
                  step="1"
                  placeholder="Any"
                  value={criteria.capacity}
                  onChange={(event) => onChange('capacity', event.target.value)}
                  aria-invalid={!validCapacity}
                  aria-describedby={!validCapacity ? 'room-capacity-error' : undefined}
                />
              </label>
              <label>
                Room type
                <select
                  value={criteria.type}
                  onChange={(event) => onChange('type', event.target.value)}
                >
                  <option value="">All types</option>
                  {options(rooms.flatMap((room) => (room.resource ? [room.resource.type] : [])))}
                </select>
              </label>
              <label>
                Facility
                <select
                  value={criteria.facility}
                  onChange={(event) => onChange('facility', event.target.value)}
                >
                  <option value="">Any facility</option>
                  {options(rooms.flatMap(roomFacilities))}
                </select>
              </label>
            </>
          )}
        </div>
        {!hasMetadata && (
          <p className="muted">
            Capacity, type, equipment, and condition are unverified in this inventory.
          </p>
        )}
      </details>
      {!validCapacity && (
        <p id="room-capacity-error" className="discovery-filter-error" role="alert">
          Enter a whole number of seats greater than zero.
        </p>
      )}
      {active.length > 0 && (
        <div className="discovery-filters__active">
          <p>
            Filtering by:{' '}
            {active
              .map(([key, value]) =>
                key === 'capacity' ? `${value}+ seats` : key === 'search' ? `“${value}”` : value,
              )
              .join(' · ')}
          </p>
          <Button variant="secondary" onClick={onReset}>
            Clear filters
          </Button>
        </div>
      )}
    </section>
  );
}
