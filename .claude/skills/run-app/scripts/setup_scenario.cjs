// The default run: a full party at full HD against a 6-Pokémon trainer, the app's most common view.
module.exports = async (h) => {
  await h.resize(1920, 1080);
  for (const name of ["Gyarados", "Onix", "Infernape", "Staraptor", "Luxray", "Roserade"]) {
    await h.clickSlot(name);
  }
  h.moveAway();
  h.say("party", JSON.stringify(await h.party()));
  h.say("trainer found", await h.trainer("Gym Leader Roark 1"));
  h.say("layout", JSON.stringify(await h.layout()));
  await h.shot("setup_party6");
};
