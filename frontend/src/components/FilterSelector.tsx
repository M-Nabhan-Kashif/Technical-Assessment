import React from 'react';
import { FilterType } from '../hooks/useVideoProcessor';

interface FilterSelectorProps {
  selectedFilter: FilterType;
  onFilterChange: (filter: FilterType) => void;
  disabled?: boolean;
}

interface FilterOption {
  id: FilterType;
  name: string;
  description: string;
  icon: string;
}

const FILTER_OPTIONS: FilterOption[] = [
  {
    id: 'grayscale',
    name: 'Grayscale',
    description: 'Convert background to black and white',
    icon: '⚫',
  },
  {
    id: 'sepia',
    name: 'Sepia',
    description: 'Apply vintage sepia tone to background',
    icon: '🟤',
  },
  {
    id: 'blur',
    name: 'Blur',
    description: 'Blur the background',
    icon: '🔵',
  },
];

const FilterSelector: React.FC<FilterSelectorProps> = ({
  selectedFilter,
  onFilterChange,
  disabled = false,
}) => {
  return (
    <div className="filter-selector">
      <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#333' }}>
        Select Background Filter
      </h3>
      <div className="filter-grid">
        {FILTER_OPTIONS.map((filter) => {
          const isSelected = selectedFilter === filter.id;
          return (
            <button
              key={filter.id}
              className={`filter-card ${isSelected ? 'filter-card-selected' : ''}`}
              onClick={() => !disabled && onFilterChange(filter.id)}
              disabled={disabled}
              type="button"
              aria-pressed={isSelected}
            >
              <div className="filter-icon">{filter.icon}</div>
              <div className="filter-name">{filter.name}</div>
              <div className="filter-description">{filter.description}</div>
              {isSelected && (
                <div className="filter-checkmark" aria-label="Selected">
                  ✓
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default FilterSelector;

