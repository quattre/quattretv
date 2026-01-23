class User {
  final int id;
  final String username;
  final String? email;
  final String? firstName;
  final String? lastName;
  final String? phone;
  final Tariff? tariff;
  final DateTime? subscriptionExpires;
  final double balance;
  final int maxDevices;
  final int maxConcurrentStreams;
  final bool isSubscriptionActive;
  final int activeDevicesCount;

  User({
    required this.id,
    required this.username,
    this.email,
    this.firstName,
    this.lastName,
    this.phone,
    this.tariff,
    this.subscriptionExpires,
    this.balance = 0,
    this.maxDevices = 5,
    this.maxConcurrentStreams = 2,
    this.isSubscriptionActive = false,
    this.activeDevicesCount = 0,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      username: json['username'],
      email: json['email'],
      firstName: json['first_name'],
      lastName: json['last_name'],
      phone: json['phone'],
      tariff: json['tariff'] != null ? Tariff.fromJson(json['tariff']) : null,
      subscriptionExpires: json['subscription_expires'] != null
          ? DateTime.parse(json['subscription_expires'])
          : null,
      balance: (json['balance'] ?? 0).toDouble(),
      maxDevices: json['max_devices'] ?? 5,
      maxConcurrentStreams: json['max_concurrent_streams'] ?? 2,
      isSubscriptionActive: json['is_subscription_active'] ?? false,
      activeDevicesCount: json['active_devices_count'] ?? 0,
    );
  }

  String get fullName {
    if (firstName == null && lastName == null) return username;
    return '${firstName ?? ''} ${lastName ?? ''}'.trim();
  }

  int? get daysUntilExpiry {
    if (subscriptionExpires == null) return null;
    return subscriptionExpires!.difference(DateTime.now()).inDays;
  }
}

class Tariff {
  final int id;
  final String name;
  final String? description;
  final double price;
  final int durationDays;
  final int maxDevices;
  final int maxConcurrentStreams;
  final bool hasTimeshift;
  final bool hasPvr;
  final bool hasVod;
  final bool hasCatchup;

  Tariff({
    required this.id,
    required this.name,
    this.description,
    required this.price,
    this.durationDays = 30,
    this.maxDevices = 5,
    this.maxConcurrentStreams = 2,
    this.hasTimeshift = true,
    this.hasPvr = true,
    this.hasVod = true,
    this.hasCatchup = true,
  });

  factory Tariff.fromJson(Map<String, dynamic> json) {
    return Tariff(
      id: json['id'],
      name: json['name'],
      description: json['description'],
      price: (json['price'] ?? 0).toDouble(),
      durationDays: json['duration_days'] ?? 30,
      maxDevices: json['max_devices'] ?? 5,
      maxConcurrentStreams: json['max_concurrent_streams'] ?? 2,
      hasTimeshift: json['has_timeshift'] ?? true,
      hasPvr: json['has_pvr'] ?? true,
      hasVod: json['has_vod'] ?? true,
      hasCatchup: json['has_catchup'] ?? true,
    );
  }
}
