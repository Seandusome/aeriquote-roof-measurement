const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('app.py','utf8');
const scope={CANADIAN_PROVINCES:new Set(['SK','AB','BC'])};vm.createContext(scope);
vm.runInContext(source.split('\n').find(l=>l.startsWith('function unitAddressSuggestion(')),scope);
assert.equal(scope.unitAddressSuggestion('115 2301 Ave C North','SK').address,'2301 Ave C North #115');
for(const [street,province] of [['2301 8 Ave NW','AB'],['2301 100 Ave NW','AB'],['2301 Ave C North #115','SK'],['115-2301 Ave C North','SK'],['115 2301 Main St','CA']])assert.equal(scope.unitAddressSuggestion(street,province),null);
console.log('PASS: ambiguous Canadian unit suggestion is explicit, numbered streets and already formatted units unchanged; US civic numbers never reinterpreted');
