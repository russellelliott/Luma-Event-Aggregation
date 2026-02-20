import React, { useState } from 'react';
import { Search, X } from 'lucide-react';

const SearchBar = ({ onSearch, className = '' }) => {
  const [localQuery, setLocalQuery] = useState('');

  const submitSearch = (value) => {
    onSearch(value);
  };
  
  const handleKeyDown = (e) => {
      if (e.key === 'Enter') {
          e.preventDefault();
          submitSearch(localQuery);
      }
  };

  const handleClear = () => {
    setLocalQuery('');
    submitSearch('');
  };

  return (
    <div className={`relative max-w-lg w-full ${className}`}>
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Search className="h-5 w-5 text-gray-400" />
      </div>
      <input
        type="text"
        className="block w-full pl-10 pr-10 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 sm:text-sm"
        placeholder="Search for events..."
        value={localQuery}
        onChange={(e) => setLocalQuery(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      {localQuery && (
        <button
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-3 flex items-center"
        >
            <X className="h-5 w-5 text-gray-400 hover:text-gray-600" />
        </button>
      )}
    </div>
  );
};

export default SearchBar;
