const {
  DeviceManagementKitBuilder,
  DeviceActionStatus,
} = require("@ledgerhq/device-management-kit");

const {
  nodeHidTransportFactory,
} = require("@ledgerhq/device-transport-kit-node-hid");

const {
  SignerSolanaBuilder,
} = require("@ledgerhq/device-signer-kit-solana");

const { firstValueFrom } = require("rxjs");

const ROBERTA_PATH = "44'/501'/1'/0'";
const EXPECTED =
  "3g8TZbnj6mnTrzS6qm1nkHUNQntrVnPD2f9bjfNpMjeU";

async function main() {
  console.log("Building Ledger DMK...");

  const dmk = new DeviceManagementKitBuilder()
    .addTransport(nodeHidTransportFactory)
    .build();

  console.log("Looking for Ledger...");

  const device = await firstValueFrom(
    dmk.startDiscovering({})
  );

  console.log("Ledger found once.");

  const sessionId = await dmk.connect({ device });

  console.log("Connected.");

  const signer = new SignerSolanaBuilder({
    dmk,
    sessionId,
  }).build();

  console.log(`Reading ${ROBERTA_PATH}...`);

  const { observable, cancel } = signer.getAddress(
    ROBERTA_PATH,
    { checkOnDevice: false, skipOpenApp: true }
  );

  await new Promise((resolve, reject) => {
    const sub = observable.subscribe({
      next: (state) => {
        console.log("");
        console.log("STATE:", state.status);

        if (state.intermediateValue !== undefined) {
          console.log(
            "INTERMEDIATE:",
            state.intermediateValue
          );
        }

        if (state.status === DeviceActionStatus.Completed) {
          console.log("");
          console.log("Ledger address:   ", state.output);
          console.log("Expected Roberta: ", EXPECTED);

          if (state.output === EXPECTED) {
            console.log("");
            console.log(
              "SUCCESS: Roberta Ledger account verified."
            );
          } else {
            console.log("");
            console.log("MISMATCH: Wrong Ledger account.");
          }

          sub.unsubscribe();
          resolve();
        }

        if (state.status === DeviceActionStatus.Error) {
          sub.unsubscribe();
          reject(state.error);
        }

        if (state.status === DeviceActionStatus.Stopped) {
          sub.unsubscribe();
          reject(new Error("Ledger action stopped."));
        }
      },

      error: (err) => {
        reject(err);
      },

      complete: () => {
        console.log("Observable completed.");
      },
    });
  });

  await dmk.disconnect({ sessionId });
}

main().catch((err) => {
  console.error("");
  console.error("LEDGER TEST FAILED:");
  console.error(err);
  process.exit(1);
});
