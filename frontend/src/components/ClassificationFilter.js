import React from 'react';
import { Tag, Users } from 'lucide-react';

const EVENT_TYPES = [
  { id: 'career_fair', label: 'Career Fair' },
  { id: 'hackathon', label: 'Hackathon' },
  { id: 'workshop', label: 'Workshop' },
  { id: 'networking', label: 'Networking' },
  { id: 'conference', label: 'Conference' },
  { id: 'demo_day', label: 'Demo Day' },
  { id: 'panel_discussion', label: 'Panel Discussion' }
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

  return (
    <div className="space-y-6">
      {/* Event Types */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-4">
          <Tag className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-800">Event Types</h3>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {EVENT_TYPES.map(type => (
            <label 
              key={type.id} 
              className={`
                flex items-center p-3 rounded-lg border cursor-pointer transition-all
                ${selectedFilters.eventTypes?.includes(type.id)
                  ? 'bg-blue-50 border-blue-200'
                  : 'hover:bg-gray-50 border-gray-200'
                }
              `}
            >
              <input
                type="checkbox"
                className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                checked={selectedFilters.eventTypes?.includes(type.id) || false}
                onChange={() => handleToggle('eventTypes', type.id)}
              />
              <span className="ml-3 text-sm font-medium text-gray-700">{type.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Audience Categories */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-4">
          <Users className="w-5 h-5 text-purple-600" />
          <h3 className="text-lg font-semibold text-gray-800">Audience</h3>
        </div>
        <div className="space-y-2">
          {AUDIENCE_CATEGORIES.map(category => (
            <label 
              key={category.id}
              className={`
                flex items-center p-3 rounded-lg border cursor-pointer transition-all
                ${selectedFilters.audienceCategories?.includes(category.id)
                  ? 'bg-purple-50 border-purple-200'
                  : 'hover:bg-gray-50 border-gray-200'
                }
              `}
            >
              <input
                type="checkbox"
                className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                checked={selectedFilters.audienceCategories?.includes(category.id) || false}
                onChange={() => handleToggle('audienceCategories', category.id)}
              />
              <span className="ml-3 text-sm font-medium text-gray-700">{category.label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
