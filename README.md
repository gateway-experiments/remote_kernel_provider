# Remote Kernel Provider

__NOTE: This repository is experimental and undergoing frequent changes!__

The Remote Kernel Provider package provides the base support for remote kernel providers.  This includes three things:

1. The base remote kernel provider class: `RemoteKernelProviderBase`
2. The `RemoteKernelManager` class that manages all instances of remote kernels
3. The base implementation for kernel lifecycle managers, whose instances are *contained* by the `RemoteKernelManager`.  That is, the `RemoteKernelManager` *has a*[n] instance of a kernel lifecycle manager that corresponds to the launching kernel provider.


Subclasses of `RemoteKernelProviderBase` are (but not limited to):
- [`YarnKernelProvider`](https://github.com/gateway-experiments/yarn_kernel_provider)
- `KubernetesKernelProvider`
- `DistributedKernelProvider`
- `DockerKernelProvider`
- `ConductorKernelProvider`

## Installation
`RemoteKernelProvider` is a pip-installable package:
```bash
pip install remote_kernel_provider
```

However, because its purely a base class, it is not usable until one of its subclass providers is also installed.
