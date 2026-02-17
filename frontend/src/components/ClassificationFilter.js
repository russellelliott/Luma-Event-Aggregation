import React from 'react';
import { Tag, Users, Bookmark } from 'lucide-react';

const EVENT_TYPES = [
  { id: 'career_fair', label: 'Career Fair' },
  { id: 'hackathon', label: 'Hackathon' },
  { id: 'workshop', label: 'Workshop' },
  { id: 'networking', label: 'Networking' },
  { id: 'conference', label: 'Conference' },
  { id: 'demo_day', label: 'Demo Day' },
  { id: 'panel_discussion', label: 'Panel' },
];

const AUDIENCE_CATEGORIES = [
  { id: 'job_seekers', label: 'Job Seekers' },
  { id: 'founder_investor', label: 'Founder / Investor' },
  { id: 'general', label: 'General' }
];

export default function ClassificationFilter({ selectedFilters, onFilterChange }) {
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

  return (
    <div className="space-y-3">
      {/* Bookmarks */}
      <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-100">
        <button
          onClick={handleBookmarkToggle}
          className={`
            w-full flex items-center justify-center gap-2 p-2 rounded-lg border transition-all text-sm font-medium
            ${selectedFilters.bookmarked
              ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
              : 'text-gray-600 hover:bg-gray-50 border-gray-200'
            }
          `}
        >
          <Bookmark className={`w-3.5 h-3.5 ${selectedFilters.bookmarked ? 'fill-current' : ''}`} />
          Show Bookmarked Only
        </button>
      </div>

      {/* Event Types */}
      <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-2">
          <Tag className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-800">Event Types</h3>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {EVENT_TYPES.map(type => (
            <button
              key={type.id}
              onClick={() => handleToggle('eventTypes', type.id)}
              className={`
                px-2.5 py-1 rounded-md text-xs font-medium border transition-all
                ${selectedFilters.eventTypes?.includes(type.id)
                  ? 'bg-blue-100 text-blue-700 border-blue-200'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                }
              `}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>

      {/* Audience Categories */}
      <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-2">
          <Users className="w-4 h-4 text-purple-600" />
          <h3 className="text-sm font-semibold text-gray-800">Audience</h3>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {AUDIENCE_CATEGORIES.map(category => (
            <button
              key={category.id}
              onClick={() => handleToggle('audienceCategories', category.id)}
              className={`
                px-2.5 py-1 rounded-md text-xs font-medium border transition-all
                ${selectedFilters.audienceCategories?.includes(category.id)
                  ? 'bg-purple-100 text-purple-700 border-purple-200'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                }
              `}
            >
              {category.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
