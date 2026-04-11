import React from 'react';
import { Tag, Bookmark, DollarSign } from 'lucide-react';

export default function ClassificationFilter({
  selectedFilters,
  onFilterChange,
  topicOptions,
  bookmarkedTopicLabels,
  bookmarkedCategoriesActive,
  onBookmarkedCategoriesToggle,
}) {
  const handleToggle = (category, value) => {
    const currentValues = selectedFilters[category] || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    
    onFilterChange(category, newValues);
  };

  const handleBookmarkToggle = () => {
    onFilterChange('bookmarked', !selectedFilters.bookmarked);
  };
  
  const handlePaidToggle = () => {
    onFilterChange('showPaid', !selectedFilters.showPaid);
  };

  return (
    <div className="space-y-3">
      {/* Search & Filter Controls */}
      <div className="grid grid-cols-2 gap-2">
        {/* Bookmarks */}
        <button
          onClick={handleBookmarkToggle}
          className={`
            flex items-center justify-center gap-2 p-2 rounded-lg border transition-all text-xs font-medium h-10
            ${selectedFilters.bookmarked
              ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
              : 'bg-white text-gray-600 hover:bg-gray-50 border-gray-200'
            }
          `}
        >
          <Bookmark className={`w-3.5 h-3.5 ${selectedFilters.bookmarked ? 'fill-current' : ''}`} />
          Bookmarks Only
        </button>

        {/* Paid Filter */}
        <button
          onClick={handlePaidToggle}
          className={`
            flex items-center justify-center gap-2 p-2 rounded-lg border transition-all text-xs font-medium h-10
            ${selectedFilters.showPaid
              ? 'bg-purple-50 text-purple-700 border-purple-200'
              : 'bg-green-50 text-green-700 border-green-200'
            }
          `}
        >
          <DollarSign className="w-3.5 h-3.5" />
          {selectedFilters.showPaid ? 'Includes Paid' : 'Free Only'}
        </button>
      </div>

      {/* Topic Clusters */}
      <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-2">
          <Tag className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-semibold text-gray-800">Description Clusters</h3>
        </div>
        <button
          onClick={onBookmarkedCategoriesToggle}
          disabled={bookmarkedTopicLabels.length === 0}
          className={`
            w-full mb-2 flex items-center justify-between gap-2 p-2.5 rounded-lg border transition-all text-[11px] font-medium
            ${bookmarkedCategoriesActive
              ? 'bg-amber-50 text-amber-700 border-amber-200 shadow-sm ring-1 ring-amber-200/70'
              : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-200'
            }
            ${bookmarkedTopicLabels.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}
          `}
          title={bookmarkedTopicLabels.length === 0 ? 'No bookmarked categories yet' : 'Select bookmarked categories'}
        >
          <span className="flex items-center gap-2 min-w-0">
            <Bookmark className={`w-3.5 h-3.5 shrink-0 ${bookmarkedCategoriesActive ? 'fill-current' : ''}`} />
            <span className="truncate">Bookmarked Categories</span>
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-inherit opacity-80">
            {bookmarkedTopicLabels.length}
          </span>
        </button>
        <div className="columns-2 gap-2 [column-fill:balance]">
          {topicOptions.map(topic => (
            (() => {
              const isBookmarkedCategory = bookmarkedCategoriesActive && bookmarkedTopicLabels.includes(topic.label);
              const isSelected = selectedFilters.topicLabels?.includes(topic.label);
              const shouldHighlight = isSelected || isBookmarkedCategory;

              return (
                <button
                  key={topic.label}
                  onClick={() => handleToggle('topicLabels', topic.label)}
                  className={`
                    mb-1.5 flex w-full items-center justify-between gap-2 break-inside-avoid rounded-md border px-2.5 py-1 text-[11px] font-medium transition-all
                    ${shouldHighlight
                      ? 'shadow-sm ring-1 ring-inset'
                      : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                    }
                  `}
                  style={{
                    backgroundColor: shouldHighlight
                      ? `${topic.color}1F`
                      : undefined,
                    borderColor: shouldHighlight ? topic.color : undefined,
                    color: shouldHighlight ? topic.color : undefined
                  }}
                >
                  <span className="min-w-0 truncate">{topic.label}</span>
                  <span
                    className="inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-semibold leading-none text-white"
                    style={{ backgroundColor: topic.color }}
                    aria-label={`${topic.count} events in ${topic.label}`}
                  >
                    {topic.count}
                  </span>
                </button>
              );
            })()
          ))}
          {topicOptions.length === 0 && (
            <span className="text-[11px] text-gray-400">No current description clusters to display.</span>
          )}
        </div>
      </div>
    </div>
  );
}
