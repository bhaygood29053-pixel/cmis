const TransportNodeHid =
  require("@ledgerhq/hw-transport-node-hid").default;

const Solana =
  require("@ledgerhq/hw-app-solana").default;

const { PublicKey } =
  require("@solana/web3.js");

const PATH = "44'/501'/1'/0'";
const EXPECTED =
  "3g8TZbnj6mnTrzS6qm1nkHUNQntrVnPD2f9bjfNpMjeU";

async function main() {
  let transport;

  try {
    console.log("Opening Ledger HID connection...");

    transport = await TransportNodeHid.open("");

    console.log("Ledger connected.");

    const solana = new Solana(transport);

    console.log(`Reading ${PATH}...`);

    const result = await solana.getAddress(PATH, false);

    const address =
      new PublicKey(result.address).toBase58();

    console.log("");
    console.log("Ledger address:   ", address);
    console.log("Expected Roberta: ", EXPECTED);

    if (address === EXPECTED) {
      console.log("");
      console.log(
        "SUCCESS: Roberta Ledger account verified."
      );
    } else {
      console.log("");
      console.log("MISMATCH: Wrong Ledger account.");
    }
  } finally {
    if (transport) {
      await transport.close();
    }
  }
}

main().catch((err) => {
  console.error("");
  console.error("LEDGER TEST FAILED:");
  console.error(err);
  process.exit(1);
});
