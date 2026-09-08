// Rendering must never displace a citizen from their physical street position.
export function citizenLayout(people, project) {
  return people.map(person => {
    const anchor = project(person.position);
    return {id: person.id, point: anchor, anchor};
  });
}
